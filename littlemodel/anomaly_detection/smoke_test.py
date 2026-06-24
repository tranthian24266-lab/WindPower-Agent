from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from runtime_common import append_log, ensure_runtime_dirs, format_traceback, relpath_str, reset_log, write_json

MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import inference

DEFAULT_INPUT = MODULE_DIR / "test_data" / "test_data_sample.csv"
AVG_PATTERN = re.compile(r"(avg|average|mean)", re.IGNORECASE)
STATS_PATTERN = re.compile(r"(^|[_\W])(min|max|std)([_\W]|$)", re.IGNORECASE)


def _load_config() -> dict:
    return yaml.safe_load((MODULE_DIR / "config.yaml").read_text(encoding="utf-8"))


def prepare_input_csv(input_path: Path, prepared_path: Path, include_stats_cols: bool, log_path: Path) -> dict:
    frame = pd.read_csv(input_path)
    config = _load_config()
    expected_features = list(config.get("feature_names", []))

    avg_cols = [column for column in frame.columns if AVG_PATTERN.search(column)]
    stats_cols = [column for column in frame.columns if STATS_PATTERN.search(column)]
    derived_cols = [column for column in frame.columns if column.endswith("_sin") or column.endswith("_cos")]
    passthrough_cols = [
        column
        for column in frame.columns
        if column in expected_features and column not in avg_cols and column not in derived_cols and column not in stats_cols
    ]

    if not avg_cols:
        raise ValueError(
            "No Avg / average / mean columns were found in the input CSV. "
            "Please provide a CARE2Compare-like file with Avg signals or override the preprocessing first."
        )

    prepared = frame.copy()
    dropped_stats = []
    if not include_stats_cols:
        dropped_stats = [column for column in stats_cols if column not in expected_features]
        prepared = prepared.drop(columns=dropped_stats, errors="ignore")

    missing_features = [column for column in expected_features if column not in prepared.columns]
    append_log(log_path, f"Avg-style signal columns detected: {avg_cols}")
    append_log(log_path, f"Derived checkpoint columns preserved: {derived_cols}")
    append_log(log_path, f"Extra checkpoint columns preserved: {passthrough_cols}")
    append_log(log_path, f"Stats-style columns detected: {stats_cols}")
    append_log(log_path, f"Stats-style columns dropped by default: {dropped_stats}")

    if missing_features:
        raise ValueError(
            "The prepared CSV is still missing checkpoint-required features: "
            f"{missing_features}. The current packaged model expects training-aligned columns."
        )

    prepared_path.parent.mkdir(parents=True, exist_ok=True)
    prepared.to_csv(prepared_path, index=False)
    append_log(log_path, f"Wrote prepared input CSV to {prepared_path}")
    return {
        "avg_columns": avg_cols,
        "stats_columns": stats_cols,
        "dropped_stats_columns": dropped_stats,
        "prepared_columns": list(prepared.columns),
        "missing_checkpoint_features": missing_features,
    }


def build_summary(input_path: Path, result: dict, output_dir: Path, log_path: Path) -> dict:
    prediction_csv = output_dir / "prediction.csv"
    score_csv = output_dir / "anomaly_scores.csv"
    plot_path = output_dir / "anomaly_plot.png"
    summary_path = output_dir / "summary.json"

    prediction_frame = pd.read_csv(prediction_csv)
    score_frame = prediction_frame[["anomaly_score", "prediction", "pred_label"]].copy()
    score_frame.insert(0, "sample_index", range(len(score_frame)))
    score_frame.to_csv(score_csv, index=False)

    plt.figure(figsize=(10, 4))
    plt.plot(score_frame["sample_index"], score_frame["anomaly_score"], linewidth=1.2, label="anomaly_score")
    plt.axhline(float(result["threshold"]), color="red", linestyle="--", linewidth=1.0, label="threshold")
    plt.xlabel("sample_index")
    plt.ylabel("anomaly_score")
    plt.title("CARE2Compare Single-File Anomaly Demo")
    plt.legend()
    plt.tight_layout()
    plt.savefig(plot_path, dpi=160)
    plt.close()

    summary = {
        "module": "health_detection",
        "model_name": "EnergyFaultDetector_Autoencoder",
        "data_source": "CARE2Compare",
        "input_file": str(input_path),
        "status": "success",
        "metrics": {
            "num_samples": int(result["num_samples"]),
            "num_anomalies": int(result["num_anomalies"]),
            "anomaly_ratio": float(result["anomaly_ratio"]),
            "mean_anomaly_score": float(result["mean_anomaly_score"]),
            "max_anomaly_score": float(result["max_anomaly_score"]),
            "threshold": float(result["threshold"]),
        },
        "artifacts": {
            "anomaly_scores": relpath_str(score_csv, MODULE_DIR),
            "figure": relpath_str(plot_path, MODULE_DIR),
            "log": relpath_str(log_path, MODULE_DIR),
            "prepared_input": relpath_str(output_dir / "prepared_input.csv", MODULE_DIR),
            "result_json": relpath_str(output_dir / "result.json", MODULE_DIR),
        },
        "error": None,
    }
    write_json(summary_path, summary)
    return summary


def run_smoke(input_path: Path, include_stats_cols: bool) -> dict:
    ensure_runtime_dirs(MODULE_DIR)
    log_path = MODULE_DIR / "logs" / "health_detection_run.log"
    output_dir = MODULE_DIR / "outputs"
    reset_log(log_path, "anomaly_detection smoke_test")
    append_log(log_path, f"Input file: {input_path}")
    append_log(log_path, f"include_stats_cols={include_stats_cols}")

    prepared_input = output_dir / "prepared_input.csv"
    prepare_input_csv(
        input_path=input_path,
        prepared_path=prepared_input,
        include_stats_cols=include_stats_cols,
        log_path=log_path,
    )

    result = inference.predict(str(prepared_input), str(output_dir))
    if result.get("status") != "success":
        raise RuntimeError(result.get("error", "anomaly inference returned a failed status"))

    summary = build_summary(input_path=input_path, result=result, output_dir=output_dir, log_path=log_path)
    append_log(log_path, f"Smoke test completed successfully. Summary: {summary['metrics']}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Path to one CARE2Compare CSV file")
    parser.add_argument("--include_stats_cols", action="store_true", help="Allow Min/Max/Std-style columns to remain")
    args = parser.parse_args()

    try:
        summary = run_smoke(input_path=Path(args.input), include_stats_cols=args.include_stats_cols)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:
        log_path = MODULE_DIR / "logs" / "health_detection_run.log"
        append_log(log_path, format_traceback(exc))
        failed = {
            "module": "health_detection",
            "model_name": "EnergyFaultDetector_Autoencoder",
            "data_source": "CARE2Compare",
            "input_file": args.input,
            "status": "fail",
            "metrics": {},
            "artifacts": {"log": relpath_str(log_path, MODULE_DIR)},
            "error": str(exc),
        }
        write_json(MODULE_DIR / "outputs" / "summary.json", failed)
        print(json.dumps(failed, indent=2, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
