from __future__ import annotations

import subprocess
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
EXAMPLES = [
    ROOT / "fault_diagnosis" / "examples" / "run_example.py",
    ROOT / "rul_prediction" / "examples" / "run_example.py",
    ROOT / "anomaly_detection" / "examples" / "run_example.py",
]


def main() -> int:
    overall_status = 0
    for script_path in EXAMPLES:
        print(f"=== Running {script_path.relative_to(ROOT)} ===")
        if not script_path.exists():
            print(f"FAILED: example script not found: {script_path}")
            overall_status = 1
            continue

        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print(result.stderr.strip())
        if result.returncode != 0:
            print(f"FAILED: {script_path.relative_to(ROOT)} exited with code {result.returncode}")
            overall_status = 1
        else:
            print("OK")
    return overall_status


if __name__ == "__main__":
    raise SystemExit(main())
