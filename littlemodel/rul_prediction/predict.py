from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from runtime_common import append_log, ensure_runtime_dirs, format_traceback, relpath_str, reset_log, write_json

MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import inference


DEFAULT_INPUT = MODULE_DIR / "test_data" / "split_60_40" / "data-20130406T221209Z.mat"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Path to one HSSB .mat input")
    parser.add_argument("--output", default=str(MODULE_DIR / "outputs" / "predict"), help="Output directory")
    args = parser.parse_args()

    ensure_runtime_dirs(MODULE_DIR)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = MODULE_DIR / "logs" / "rul_hsb_run.log"
    reset_log(log_path, "rul_prediction predict")

    try:
        result = inference.predict(args.input, str(output_dir))
        if result.get("status") != "success":
            raise RuntimeError(result.get("error", "rul inference returned a failed status"))

        payload = {
            "module": "fault_prediction_rul",
            "model_name": result.get("model_name", "HSSB SVR Multi-feature RUL Prediction Model"),
            "input_file": args.input,
            "status": "success",
            "prediction": {
                "fault_class": None,
                "fault_probability": None,
                "health_score": max(0.0, min(1.0, float(result["rul_clipped"]) / 50.0)),
                "is_anomaly": None,
                "anomaly_score": None,
                "rul": float(result["rul_raw"]),
            },
            "artifacts": {
                "result_json": relpath_str(output_dir / "result.json", MODULE_DIR),
                "feature_csv": relpath_str(output_dir / "feature.csv", MODULE_DIR),
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
            "module": "fault_prediction_rul",
            "model_name": "HSSB SVR Multi-feature RUL Prediction Model",
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
