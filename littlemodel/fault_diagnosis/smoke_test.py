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


DEFAULT_INPUT = MODULE_DIR / "test_data" / "test_sensor1_x.npy"


def run_smoke(input_path: Path) -> dict:
    ensure_runtime_dirs(MODULE_DIR)
    log_path = MODULE_DIR / "logs" / "fault_diagnosis_run.log"
    output_dir = MODULE_DIR / "outputs"
    reset_log(log_path, "fault_diagnosis smoke_test")
    append_log(log_path, f"Input file: {input_path}")

    result = inference.predict(str(input_path), str(output_dir))
    if result.get("status") != "success":
        raise RuntimeError(result.get("error", "fault diagnosis inference returned a failed status"))

    summary = {
        "module": "fault_diagnosis",
        "model_name": result.get("model_name", "NREL_Binary_MSCNN_BiLSTM"),
        "data_source": "packaged_test_data",
        "input_file": str(input_path),
        "status": "success",
        "metrics": {
            "predicted_class": result["prediction"],
            "fault_probability": float(result["confidence"]),
            "num_windows": int(result["preprocess"]["num_windows"]),
        },
        "artifacts": {
            "prediction_csv": relpath_str(output_dir / "prediction.csv", MODULE_DIR),
            "result_json": relpath_str(output_dir / "result.json", MODULE_DIR),
            "log": relpath_str(log_path, MODULE_DIR),
        },
        "error": None,
    }
    write_json(output_dir / "summary.json", summary)
    append_log(log_path, f"Smoke test completed successfully: {summary['metrics']}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Path to one .mat, .csv, or .npy input")
    args = parser.parse_args()

    try:
        summary = run_smoke(input_path=Path(args.input))
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:
        log_path = MODULE_DIR / "logs" / "fault_diagnosis_run.log"
        append_log(log_path, format_traceback(exc))
        failed = {
            "module": "fault_diagnosis",
            "model_name": "NREL_Binary_MSCNN_BiLSTM",
            "data_source": "packaged_test_data",
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
