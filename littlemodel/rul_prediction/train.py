from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from runtime_common import append_log, ensure_runtime_dirs, format_traceback, relpath_str, reset_log, write_json

MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import inference
from scripts.feature_extraction import compute_all_features, load_vibration_signal


DEFAULT_DATA_DIR = MODULE_DIR / "test_data" / "split_60_40"
DATE_PATTERN = re.compile(r"data-(\d{8}T\d{6}Z)\.mat$", re.IGNORECASE)


def _date_string(path: Path) -> str:
    match = DATE_PATTERN.search(path.name)
    return match.group(1) if match else path.stem


def run_baseline(data_dir: Path) -> dict:
    ensure_runtime_dirs(MODULE_DIR)
    output_dir = MODULE_DIR / "outputs"
    log_path = MODULE_DIR / "logs" / "rul_hsb_run.log"
    reset_log(log_path, "rul_prediction baseline train wrapper")
    append_log(log_path, f"Data directory: {data_dir}")
    append_log(
        log_path,
        "This wrapper builds a minimal degradation baseline over packaged .mat files. "
        "It does not execute the original GRU notebook path by default.",
    )

    files = sorted(data_dir.glob("*.mat"))
    if not files:
        raise FileNotFoundError(f"No .mat files found under {data_dir}")

    payload = inference._load_payload()
    model = payload["model"]
    feature_names = list(payload["feature_names"])
    records = []
    for idx, mat_path in enumerate(files):
        signal, input_meta = load_vibration_signal(mat_path)
        features, feature_meta = compute_all_features(signal=signal)
        missing = [name for name in feature_names if name not in features]
        if missing:
            raise ValueError(f"Missing required features for {mat_path.name}: {missing}")
        feature_vector = [[features[name] for name in feature_names]]
        rul_raw = float(model.predict(feature_vector)[0])
        records.append(
            {
                "sequence_index": idx,
                "file_name": mat_path.name,
                "date_string": _date_string(mat_path),
                "signal_length": input_meta["signal_length"],
                "rul_raw": rul_raw,
                "health_score": max(0.0, min(1.0, rul_raw / 50.0)),
                **{name: float(features[name]) for name in features.keys()},
                **{f"meta_{key}": value for key, value in feature_meta.items()},
            }
        )

    frame = pd.DataFrame(records).sort_values("date_string").reset_index(drop=True)
    features_csv = output_dir / "degradation_features.csv"
    frame.to_csv(features_csv, index=False)

    fig, ax1 = plt.subplots(figsize=(10, 4.8))
    ax1.plot(frame["sequence_index"], frame["rul_raw"], marker="o", linewidth=1.2, label="predicted_rul_raw", color="#1f77b4")
    ax1.set_xlabel("sequence_index")
    ax1.set_ylabel("predicted_rul_raw")
    ax1.set_title("HSSB Baseline Degradation Trend")

    ax2 = ax1.twinx()
    ax2.plot(
        frame["sequence_index"],
        frame["sk_area_positive"],
        marker="s",
        linewidth=1.0,
        label="sk_area_positive",
        color="#ff7f0e",
        alpha=0.75,
    )
    ax2.set_ylabel("sk_area_positive")

    lines, labels = [], []
    for ax in (ax1, ax2):
        line, label = ax.get_legend_handles_labels()
        lines.extend(line)
        labels.extend(label)
    ax1.legend(lines, labels, loc="best")
    fig.tight_layout()
    plot_path = output_dir / "health_indicator.png"
    fig.savefig(plot_path, dpi=160)
    plt.close(fig)

    metrics = {
        "num_files": int(len(frame)),
        "rul_raw_min": float(frame["rul_raw"].min()),
        "rul_raw_max": float(frame["rul_raw"].max()),
        "rul_raw_mean": float(frame["rul_raw"].mean()),
        "health_score_mean": float(frame["health_score"].mean()),
    }
    metrics_path = output_dir / "rul_or_degradation_metrics.json"
    write_json(metrics_path, metrics)

    summary = {
        "module": "fault_prediction_rul",
        "model_name": "HSB_Degradation_Baseline",
        "data_source": "WindTurbineHighSpeedBearingPrognosis-Data",
        "input_file": str(data_dir),
        "status": "success",
        "metrics": metrics,
        "artifacts": {
            "features_csv": relpath_str(features_csv, MODULE_DIR),
            "health_indicator_plot": relpath_str(plot_path, MODULE_DIR),
            "log": relpath_str(log_path, MODULE_DIR),
            "metrics_json": relpath_str(metrics_path, MODULE_DIR),
        },
        "error": None,
    }
    write_json(output_dir / "summary.json", summary)
    append_log(log_path, f"Baseline summary: {metrics}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="Directory that contains one ordered HSSB .mat split")
    args = parser.parse_args()

    try:
        summary = run_baseline(data_dir=Path(args.data_dir))
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:
        log_path = MODULE_DIR / "logs" / "rul_hsb_run.log"
        append_log(log_path, format_traceback(exc))
        failed = {
            "module": "fault_prediction_rul",
            "model_name": "HSB_Degradation_Baseline",
            "data_source": "WindTurbineHighSpeedBearingPrognosis-Data",
            "input_file": args.data_dir,
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
