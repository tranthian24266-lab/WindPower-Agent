from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ModelRegistryError(RuntimeError):
    """Raised when the local model registry cannot be read safely."""


class ModelRegistryService:
    def __init__(self, littlemodel_root: Path):
        self.littlemodel_root = Path(littlemodel_root)

    @property
    def registry_path(self) -> Path:
        return self.littlemodel_root / "model_registry.json"

    def load_registry(self) -> dict[str, Any]:
        if not self.littlemodel_root.exists():
            raise ModelRegistryError(f"Littlemodel root does not exist: {self.littlemodel_root}")
        if not self.registry_path.exists():
            raise ModelRegistryError(f"Registry file does not exist: {self.registry_path}")

        try:
            payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ModelRegistryError(f"Failed to parse model registry: {exc}") from exc

        models = payload.get("models")
        if not isinstance(models, list):
            raise ModelRegistryError("Registry payload is missing a 'models' list.")
        return payload

    def list_models(self) -> list[dict[str, Any]]:
        payload = self.load_registry()
        registry_version = payload.get("version", "1.0.0")
        return [self._enrich_entry(entry, registry_version) for entry in payload["models"]]

    def get_active_model(self, task_type: str) -> dict[str, Any]:
        for entry in self.list_models():
            if entry["task_type"] == task_type and entry["status"] == "active":
                return entry
        raise ModelRegistryError(f"No active model found for task_type '{task_type}'.")

    def resolve_model_dir(self, model_entry: dict[str, Any]) -> Path:
        model_dir = self.littlemodel_root / model_entry["model_dir"]
        if not model_dir.exists():
            raise ModelRegistryError(f"Model directory does not exist: {model_dir}")
        return model_dir

    def resolve_entrypoint(self, model_entry: dict[str, Any]) -> tuple[Path, str]:
        model_dir = self.resolve_model_dir(model_entry)
        entrypoint = model_entry["entrypoint"]
        module_rel, function_name = entrypoint.split(":", maxsplit=1)
        module_path = model_dir / module_rel
        if not module_path.exists():
            raise ModelRegistryError(f"Entrypoint file does not exist: {module_path}")
        return module_path, function_name

    def _enrich_entry(self, entry: dict[str, Any], registry_version: str) -> dict[str, Any]:
        required = ["model_id", "task_type", "model_dir", "entrypoint", "status"]
        missing = [field for field in required if field not in entry]
        if missing:
            raise ModelRegistryError(f"Registry entry missing required fields: {missing}")

        model_dir = self.littlemodel_root / entry["model_dir"]
        model_card = self._load_json_if_exists(model_dir / "model_card.json")
        readme_summary = self._load_readme_summary(model_dir / "README.md")

        return {
            "model_id": entry["model_id"],
            "task_type": entry["task_type"],
            "model_dir": entry["model_dir"],
            "entrypoint": entry["entrypoint"],
            "status": entry["status"],
            "version": model_card.get("model_version") or registry_version,
            "model_name": model_card.get("model_name") or entry["model_id"],
            "paper_title": model_card.get("paper_title"),
            "dataset": model_card.get("dataset"),
            "input_format": model_card.get("input_format"),
            "output_labels": model_card.get("output_labels"),
            "feature_names": model_card.get("feature_names"),
            "threshold": model_card.get("threshold"),
            "limitations": model_card.get("limitations") or [],
            "readme_summary": readme_summary,
        }

    def _load_json_if_exists(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ModelRegistryError(f"Failed to parse JSON file {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ModelRegistryError(f"Expected JSON object in {path}.")
        return payload

    def _load_readme_summary(self, path: Path) -> str | None:
        if not path.exists():
            return None

        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
        summary_parts: list[str] = []
        for line in lines:
            if not line or line.startswith("#"):
                continue
            summary_parts.append(line)
            if len(" ".join(summary_parts)) >= 220:
                break
        if not summary_parts:
            return None
        summary = " ".join(summary_parts)
        return summary[:220].rstrip()
