from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid4

from app.core.model_catalog import ModelCatalogService, ModelValidationRunRecord, to_json_text
from app.core.model_registry import ModelRegistryService


class ModelValidationError(RuntimeError):
    """Raised when a catalog version cannot be validated safely."""


@dataclass(frozen=True)
class ModelValidationResult:
    validation_run_id: str
    status: str
    summary: str
    details: dict[str, Any]


class ModelValidationService:
    def __init__(self, database_path: Path, littlemodel_root: Path):
        self.catalog = ModelCatalogService(database_path)
        self.littlemodel_root = Path(littlemodel_root)
        self.registry = ModelRegistryService(self.littlemodel_root)

    def validate_catalog_version(self, model_version_id: str) -> ModelValidationResult:
        version = self.catalog.get_model_version_detail(model_version_id)
        if version is None:
            raise ModelValidationError(f"Model version does not exist: {model_version_id}")
        validation_run_id = uuid4().hex
        started_at = _utcnow()

        try:
            details = self._collect_validation_details(version)
            result = ModelValidationResult(
                validation_run_id=validation_run_id,
                status="passed",
                summary="Model directory, entrypoint, metadata and smoke test all passed.",
                details=details,
            )
            with self.catalog.database.connect() as connection:
                self.catalog.record_validation_run(
                    connection,
                    ModelValidationRunRecord(
                        validation_run_id=validation_run_id,
                        model_version_id=model_version_id,
                        validation_type="smoke",
                        status=result.status,
                        summary=result.summary,
                        details_json=to_json_text(result.details),
                        started_at=started_at,
                        finished_at=_utcnow(),
                    ),
                )
                self.catalog.update_model_version_validation(
                    connection,
                    model_version_id,
                    validation_status="passed",
                    last_validated_at=_utcnow(),
                )
            return result
        except ModelValidationError as exc:
            details = {"error": str(exc)}
            with self.catalog.database.connect() as connection:
                self.catalog.record_validation_run(
                    connection,
                    ModelValidationRunRecord(
                        validation_run_id=validation_run_id,
                        model_version_id=model_version_id,
                        validation_type="smoke",
                        status="failed",
                        summary=str(exc),
                        details_json=to_json_text(details),
                        started_at=started_at,
                        finished_at=_utcnow(),
                    ),
                )
                self.catalog.update_model_version_validation(
                    connection,
                    model_version_id,
                    validation_status="failed",
                    last_validated_at=_utcnow(),
                )
            raise

    def _collect_validation_details(self, version: dict[str, Any]) -> dict[str, Any]:
        model_entry = {
            "model_dir": version["model_dir"],
            "entrypoint": version["entrypoint"],
        }
        model_dir = self.registry.resolve_model_dir(model_entry)
        module_path, function_name = self.registry.resolve_entrypoint(model_entry)

        model_card = self._load_json(model_dir / "model_card.json")
        if "model_name" not in model_card:
            raise ModelValidationError(f"model_card.json is incomplete for {version['model_version_id']}")

        sample_input = self._find_smoke_input(model_dir)
        smoke_output = self._run_smoke_test(module_path, function_name, sample_input)

        return {
            "model_dir_exists": True,
            "entrypoint_exists": True,
            "model_card": {
                "path": str(model_dir / "model_card.json"),
                "model_name": model_card.get("model_name"),
                "model_version": model_card.get("model_version") or version.get("version"),
            },
            "smoke_input": str(sample_input),
            "smoke_output_summary": _summarize_smoke_output(smoke_output),
        }

    def _find_smoke_input(self, model_dir: Path) -> Path:
        test_data_dir = model_dir / "test_data"
        if not test_data_dir.exists():
            raise ModelValidationError(f"Smoke test data directory does not exist: {test_data_dir}")

        for pattern in ("*.npy", "*.csv", "*.mat", "*.npz"):
            matches = sorted(test_data_dir.rglob(pattern))
            if matches:
                return matches[0]
        raise ModelValidationError(f"No smoke test sample found under {test_data_dir}")

    def _run_smoke_test(self, module_path: Path, function_name: str, sample_input: Path) -> Any:
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "validation-output"
            output_dir.mkdir(parents=True, exist_ok=True)
            module = self._load_module(module_path)
            predict_fn = getattr(module, function_name, None)
            if predict_fn is None or not callable(predict_fn):
                raise ModelValidationError(f"Model entrypoint '{function_name}' is not callable in {module_path}")
            try:
                result = predict_fn(str(sample_input), str(output_dir), {})
            except Exception as exc:  # pragma: no cover
                raise ModelValidationError(f"Smoke test failed for {module_path}: {exc}") from exc
        return result

    def _load_module(self, module_path: Path):
        spec = importlib.util.spec_from_file_location(f"windpower_validation_{uuid4().hex}", module_path)
        if spec is None or spec.loader is None:
            raise ModelValidationError(f"Cannot load module from {module_path}")

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

    def _load_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise ModelValidationError(f"Required metadata file does not exist: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ModelValidationError(f"Failed to parse JSON file {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ModelValidationError(f"Expected JSON object in {path}")
        return payload


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _summarize_smoke_output(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {
            "type": "dict",
            "keys": sorted(str(key) for key in value.keys())[:20],
            "status": value.get("status"),
            "task_type": value.get("task_type"),
        }
    return {"type": type(value).__name__}
