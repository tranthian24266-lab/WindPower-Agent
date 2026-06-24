from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from runtime_common import append_log, ensure_runtime_dirs, format_traceback, reset_log, write_json


MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = MODULE_DIR / "test_data" / "test_data_sample.csv"
AVG_PATTERN = re.compile(r"(avg|average|mean)", re.IGNORECASE)
STATS_PATTERN = re.compile(r"(^|[_\W])(min|max|std)([_\W]|$)", re.IGNORECASE)


def _load_config() -> dict:
    return yaml.safe_load((MODULE_DIR / "config.yaml").read_text(encoding="utf-8"))


def inspect_columns(input_path: Path, include_stats_cols: bool) -> dict:
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

    prepared = frame.copy()
    dropped_stats = []
    if not include_stats_cols:
        dropped_stats = [column for column in stats_cols if column not in expected_features]
        prepared = prepared.drop(columns=dropped_stats, errors="ignore")

    missing_features = [column for column in expected_features if column not in prepared.columns]
    if not avg_cols:
        raise ValueError(
            "No Avg / average / mean columns were found in the input CSV. "
            "This demo defaults to Avg-style CARE2Compare signals before any optional statistical columns."
        )

    return {
        "num_rows": int(len(frame)),
        "num_columns": int(len(frame.columns)),
        "avg_columns": avg_cols,
        "stats_columns": stats_cols,
        "derived_columns": derived_cols,
        "passthrough_checkpoint_columns": passthrough_cols,
        "dropped_stats_columns": dropped_stats,
        "missing_checkpoint_features": missing_features,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Path to one CARE2Compare CSV file")
    parser.add_argument("--include_stats_cols", action="store_true", help="Allow Min/Max/Std-style columns to remain")
    args = parser.parse_args()

    ensure_runtime_dirs(MODULE_DIR)
    log_path = MODULE_DIR / "logs" / "health_detection_run.log"
    summary_path = MODULE_DIR / "outputs" / "data_check_summary.json"
    reset_log(log_path, "anomaly_detection data_check")

    try:
        input_path = Path(args.input)
        append_log(log_path, f"Inspecting input file: {input_path}")
        report = inspect_columns(input_path=input_path, include_stats_cols=args.include_stats_cols)
        append_log(log_path, f"Rows={report['num_rows']}, columns={report['num_columns']}")
        append_log(log_path, f"Avg-style columns kept as the default signal pool: {report['avg_columns']}")
        append_log(log_path, f"Detected Min/Max/Std-style columns: {report['stats_columns']}")
        append_log(log_path, f"Default-dropped stats columns: {report['dropped_stats_columns']}")
        append_log(log_path, f"Training-aligned extra columns already present: {report['derived_columns'] + report['passthrough_checkpoint_columns']}")
        append_log(log_path, f"Missing checkpoint features after current selection: {report['missing_checkpoint_features']}")
        payload = {"status": "success", "input_file": str(input_path), "report": report, "error": None}
        write_json(summary_path, payload)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:
        append_log(log_path, format_traceback(exc))
        payload = {"status": "fail", "input_file": args.input, "report": {}, "error": str(exc)}
        write_json(summary_path, payload)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
