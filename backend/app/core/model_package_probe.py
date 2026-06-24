from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from uuid import uuid4


def _load_module(module_path: Path):
    spec = importlib.util.spec_from_file_location(f"model_package_probe_{uuid4().hex}", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load model entrypoint: {module_path}")
    module = importlib.util.module_from_spec(spec)
    original_sys_path = sys.path.copy()
    try:
        sys.path.insert(0, str(module_path.parent))
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = original_sys_path
    return module


def main() -> int:
    if len(sys.argv) != 6:
        raise SystemExit("usage: model_package_probe.py PACKAGE_DIR ENTRYPOINT SAMPLE_PATH OUTPUT_DIR RESULT_PATH")

    package_dir = Path(sys.argv[1]).resolve()
    module_rel, function_name = sys.argv[2].split(":", maxsplit=1)
    sample_path = Path(sys.argv[3]).resolve()
    output_dir = Path(sys.argv[4]).resolve()
    result_path = Path(sys.argv[5]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    module = _load_module(package_dir / module_rel)
    predict_fn = getattr(module, function_name, None)
    if predict_fn is None or not callable(predict_fn):
        raise RuntimeError(f"Entrypoint function is not callable: {function_name}")

    result = predict_fn(str(sample_path), str(output_dir), {})
    if not isinstance(result, dict):
        raise RuntimeError("predict() must return a dictionary")
    result_path.write_text(json.dumps(result, ensure_ascii=False, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
