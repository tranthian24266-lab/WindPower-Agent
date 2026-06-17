from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any
from uuid import uuid4

import numpy as np

from app.core.file_manager import FileManagerError, FileManagerService
from app.core.model_router import ModelRouterService, ModelSelectionRequest
from app.core.model_registry import ModelRegistryError, ModelRegistryService
from app.core.settings import Settings


class ModelRunnerError(RuntimeError):
    """Raised when unified model execution fails."""


class ModelRunnerService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.file_manager = FileManagerService(settings.uploads_path)
        self.registry = ModelRegistryService(settings.resolved_littlemodel_root)
        self.router = ModelRouterService(
            settings.database_path,
            settings.resolved_littlemodel_root,
            catalog_enabled=settings.model_catalog_enabled,
            fallback_to_v1=settings.model_router_fallback_to_v1,
            default_alias=settings.model_catalog_default_alias,
        )

    def run_diagnosis(self, file_id: str, task_type: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        file_meta = self.file_manager.get_file_metadata(file_id)
        selection = self.router.select_model(
            ModelSelectionRequest(
                task_type=task_type,
                input_format=file_meta.get("suffix"),
                preferred_alias=(options or {}).get("preferred_alias"),
                preferred_model_id=(options or {}).get("preferred_model_id"),
            )
        )
        model_entry = {
            "model_id": selection.legacy_model_id,
            "model_name": selection.model_name,
            "model_dir": selection.model_dir,
            "entrypoint": selection.entrypoint,
        }
        module_path, function_name = self.registry.resolve_entrypoint(model_entry)

        case_id = uuid4().hex
        output_dir = self.settings.outputs_path / case_id
        output_dir.mkdir(parents=True, exist_ok=True)

        module = self._load_module(module_path, case_id)
        predict_fn = getattr(module, function_name, None)
        if predict_fn is None or not callable(predict_fn):
            raise ModelRunnerError(f"Model entrypoint '{function_name}' is not callable in {module_path}.")

        try:
            raw_result = predict_fn(file_meta["stored_path"], str(output_dir), options or {})
        except Exception as exc:  # pragma: no cover - protects real runtime edge cases
            self._write_failed_result(output_dir, task_type, str(exc))
            raise ModelRunnerError(f"Model execution failed for task_type '{task_type}': {exc}") from exc

        result = self._json_safe(raw_result)
        if not isinstance(result, dict):
            self._write_failed_result(output_dir, task_type, "Model result is not a JSON object.")
            raise ModelRunnerError("Model result must be a JSON object.")

        response = {
            "status": result.get("status", "unknown"),
            "case_id": case_id,
            "file_id": file_id,
            "task_type": result.get("task_type", task_type),
            "model_id": result.get("model_id", model_entry["model_id"]),
            "model_name": result.get("model_name", model_entry.get("model_name")),
            "model_version_id": selection.model_version_id,
            "model_alias": selection.model_alias,
            "selection_reason": selection.selection_reason,
            "risk_level": result.get("risk_level"),
            "output_dir": str(output_dir),
            "result_json_path": str(output_dir / "result.json"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "result": result,
        }
        return response

    def _load_module(self, module_path: Path, case_id: str):
        spec = importlib.util.spec_from_file_location(f"windpower_model_{case_id}", module_path)
        if spec is None or spec.loader is None:
            raise ModelRunnerError(f"Cannot load module from {module_path}.")

        module = importlib.util.module_from_spec(spec)
        helper_names = ["model", "preprocess", "feature_extraction"]
        original_sys_path = sys.path.copy()
        for helper_name in helper_names:
            if helper_name in sys.modules:
                del sys.modules[helper_name]
        try:
            sys.path.insert(0, str(module_path.parent))
            spec.loader.exec_module(module)
        finally:
            sys.path[:] = original_sys_path
            for helper_name in helper_names:
                sys.modules.pop(helper_name, None)
        return module

    def _write_failed_result(self, output_dir: Path, task_type: str, error: str) -> None:
        payload = {"status": "failed", "task_type": task_type, "error": error}
        (output_dir / "result.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def _json_safe(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): self._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._json_safe(item) for item in value]
        if isinstance(value, np.floating):
            return float(value)
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, Path):
            return str(value)
        return value
