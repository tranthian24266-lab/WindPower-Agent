from __future__ import annotations

import json
from pathlib import Path
import sys

CURRENT_DIR = Path(__file__).resolve().parent
MODEL_DIR = CURRENT_DIR.parent
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))

from inference import predict


def main() -> int:
    input_path = MODEL_DIR / "test_data" / "split_60_40" / "data-20130406T221209Z.mat"
    output_dir = MODEL_DIR / "examples" / "outputs"
    result = predict(str(input_path), str(output_dir))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
