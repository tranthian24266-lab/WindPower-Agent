from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np
from scipy.io import loadmat

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from runtime_common import append_log, ensure_runtime_dirs, format_traceback, reset_log, write_json


MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = MODULE_DIR / "test_data"


def inspect_mat(input_path: Path) -> dict:
    data = loadmat(input_path, squeeze_me=True, struct_as_record=False)
    visible = {key: value for key, value in data.items() if not key.startswith("__")}
    variables = {}
    for key, value in visible.items():
        array = np.asarray(value)
        variables[key] = {
            "shape": list(array.shape),
            "dtype": str(array.dtype),
            "size": int(array.size),
        }
    return {"file": str(input_path), "variables": variables}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="Directory that contains HSSB .mat files")
    args = parser.parse_args()

    ensure_runtime_dirs(MODULE_DIR)
    log_path = MODULE_DIR / "logs" / "rul_data_check.log"
    summary_path = MODULE_DIR / "outputs" / "data_check_summary.json"
    reset_log(log_path, "rul_prediction data_check")

    try:
        data_dir = Path(args.data_dir)
        mat_files = sorted(data_dir.rglob("*.mat"))
        if not mat_files:
            raise FileNotFoundError(f"No .mat files found under {data_dir}")
        sample_files = random.sample(mat_files, k=min(3, len(mat_files)))
        report = [inspect_mat(path) for path in sample_files]
        for item in report:
            append_log(log_path, json.dumps(item, ensure_ascii=False))
        payload = {
            "status": "success",
            "data_dir": str(data_dir),
            "num_available_files": len(mat_files),
            "samples": report,
            "error": None,
        }
        write_json(summary_path, payload)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:
        append_log(log_path, format_traceback(exc))
        payload = {
            "status": "fail",
            "data_dir": args.data_dir,
            "num_available_files": 0,
            "samples": [],
            "error": str(exc),
        }
        write_json(summary_path, payload)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
