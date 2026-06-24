from __future__ import annotations

import argparse
import json
from pathlib import Path

from smoke_test import DEFAULT_INPUT, MODULE_DIR, run_smoke
from runtime_common import append_log


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Path to one CARE2Compare CSV file")
    parser.add_argument("--include_stats_cols", action="store_true", help="Allow Min/Max/Std-style columns to remain")
    args = parser.parse_args()

    summary = run_smoke(input_path=Path(args.input), include_stats_cols=args.include_stats_cols)
    log_path = MODULE_DIR / "logs" / "health_detection_run.log"
    append_log(
        log_path,
        "train.py completed by running the packaged detector demo with the existing checkpoint. "
        "This wrapper does not refit a new EnergyFaultDetector model yet.",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
