from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
BUILT_IN_WEIGHTS = {
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
    registry_models: list[dict[str, object]] = []
    registry_path = ROOT / "model_registry.json"
    if not registry_path.exists():
        errors.append("Missing root model_registry.json")
    else:
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            if not isinstance(registry.get("models"), list):
                errors.append("model_registry.json does not contain a models list")
            else:
                registry_models = registry["models"]
        except Exception as exc:
            errors.append(f"Failed to parse model_registry.json: {exc}")

    seen_model_ids: set[str] = set()
    active_by_task: dict[str, list[str]] = {}
    for entry in registry_models:
        model_id = str(entry.get("model_id") or "")
        model_dir_name = str(entry.get("model_dir") or "")
        task_type = str(entry.get("task_type") or "")
        if not model_id or not model_dir_name or not task_type:
            errors.append(f"Registry entry is missing model_id, model_dir or task_type: {entry}")
            continue
        if model_id in seen_model_ids:
            errors.append(f"Duplicate model_id in registry: {model_id}")
        seen_model_ids.add(model_id)
        if entry.get("status") == "active":
            active_by_task.setdefault(task_type, []).append(model_id)

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
            model_dir / "weights",
            model_dir / "test_data",
        ]
        for required_path in required_paths:
            if not required_path.exists():
                errors.append(f"Missing required file: {required_path}")

        default_weight = BUILT_IN_WEIGHTS.get(model_dir_name)
        if default_weight and not (model_dir / "weights" / default_weight).exists():
            errors.append(f"Missing built-in default weight: {model_dir / 'weights' / default_weight}")
        weights_dir = model_dir / "weights"
        if weights_dir.is_dir() and not any(path.is_file() for path in weights_dir.rglob("*")):
            errors.append(f"Weights directory is empty: {weights_dir}")

        inference_path = model_dir / "inference.py"
        if inference_path.exists():
            try:
                module = _load_module(f"validate_{model_dir_name}", inference_path)
                if not hasattr(module, "predict") or not callable(module.predict):
                    errors.append(f"{inference_path} does not expose callable predict")
            except Exception as exc:
                errors.append(f"Failed to import {inference_path}: {exc}")

    for task_type, model_ids in active_by_task.items():
        if len(model_ids) > 1:
            errors.append(f"Multiple active models for task_type {task_type}: {model_ids}")

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
