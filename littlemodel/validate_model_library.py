from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
EXPECTED = {
    "fault_diagnosis": "sensor1_mscnn_bilstm_binary_best.pth",
    "rul_prediction": "svr_demo_multifeature_60_40.joblib",
    "anomaly_detection": "best_anomaly_model.pt",
}


def _load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {file_path}")
    module = importlib.util.module_from_spec(spec)
    for helper_name in ["model", "preprocess", "feature_extraction"]:
        if helper_name in sys.modules:
            del sys.modules[helper_name]
    sys.path.insert(0, str(file_path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        if sys.path and sys.path[0] == str(file_path.parent):
            sys.path.pop(0)
    return module


def validate() -> list[str]:
    errors: list[str] = []
    registry_path = ROOT / "model_registry.json"
    if not registry_path.exists():
        errors.append("Missing root model_registry.json")
    else:
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            if not isinstance(registry.get("models"), list) or len(registry["models"]) != 3:
                errors.append("model_registry.json does not contain three registered models")
        except Exception as exc:
            errors.append(f"Failed to parse model_registry.json: {exc}")

    for model_dir_name, default_weight in EXPECTED.items():
        model_dir = ROOT / model_dir_name
        if not model_dir.is_dir():
            errors.append(f"Missing model directory: {model_dir_name}")
            continue

        required_paths = [
            model_dir / "README.md",
            model_dir / "model_card.json",
            model_dir / "config.yaml",
            model_dir / "inference.py",
            model_dir / "requirements.txt",
            model_dir / "examples" / "run_example.py",
            model_dir / "weights" / default_weight,
        ]
        for required_path in required_paths:
            if not required_path.exists():
                errors.append(f"Missing required file: {required_path}")

        inference_path = model_dir / "inference.py"
        if inference_path.exists():
            try:
                module = _load_module(f"validate_{model_dir_name}", inference_path)
                if not hasattr(module, "predict") or not callable(module.predict):
                    errors.append(f"{inference_path} does not expose callable predict")
            except Exception as exc:
                errors.append(f"Failed to import {inference_path}: {exc}")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
