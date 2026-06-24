from __future__ import annotations

import argparse
import json
from pathlib import Path

from smoke_test import DEFAULT_INPUT, MODULE_DIR, prepare_input_csv
from runtime_common import append_log, ensure_runtime_dirs, format_traceback, relpath_str, reset_log, write_json

import inference


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Path to one CARE2Compare CSV file")
    parser.add_argument("--output", default=str(MODULE_DIR / "outputs" / "predict"), help="Output directory")
    parser.add_argument("--include_stats_cols", action="store_true", help="Allow Min/Max/Std-style columns to remain")
    args = parser.parse_args()

    ensure_runtime_dirs(MODULE_DIR)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = MODULE_DIR / "logs" / "health_detection_run.log"
    reset_log(log_path, "anomaly_detection predict")

    try:
        input_path = Path(args.input)
        prepared_input = output_dir / "prepared_input.csv"
        prepare_input_csv(
            input_path=input_path,
            prepared_path=prepared_input,
            include_stats_cols=args.include_stats_cols,
            log_path=log_path,
        )
        result = inference.predict(str(prepared_input), str(output_dir))
        if result.get("status") != "success":
            raise RuntimeError(result.get("error", "anomaly inference returned a failed status"))

        payload = {
            "module": "health_detection",
            "model_name": result.get("model_name", "EnergyFaultDetector_Autoencoder"),
            "input_file": str(input_path),
            "status": "success",
            "prediction": {
                "fault_class": None,
                "fault_probability": None,
                "health_score": max(0.0, 1.0 - float(result["anomaly_ratio"])),
                "is_anomaly": bool(float(result["anomaly_ratio"]) > 0.0),
                "anomaly_score": float(result["mean_anomaly_score"]),
                "rul": None,
            },
            "artifacts": {
                "prepared_input": relpath_str(prepared_input, MODULE_DIR),
                "result_json": relpath_str(output_dir / "result.json", MODULE_DIR),
                "prediction_csv": relpath_str(output_dir / "prediction.csv", MODULE_DIR),
                "log": relpath_str(log_path, MODULE_DIR),
            },
            "error": None,
        }
        write_json(output_dir / "predict_result.json", payload)
        append_log(log_path, f"Unified predict payload written to {output_dir / 'predict_result.json'}")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:
        append_log(log_path, format_traceback(exc))
        failed = {
            "module": "health_detection",
            "model_name": "EnergyFaultDetector_Autoencoder",
            "input_file": args.input,
            "status": "fail",
            "prediction": {
                "fault_class": None,
                "fault_probability": None,
                "health_score": None,
                "is_anomaly": None,
                "anomaly_score": None,
                "rul": None,
            },
            "artifacts": {"log": relpath_str(log_path, MODULE_DIR)},
            "error": str(exc),
        }
        write_json(output_dir / "predict_result.json", failed)
        print(json.dumps(failed, indent=2, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
