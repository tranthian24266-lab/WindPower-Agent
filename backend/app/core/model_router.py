from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.model_catalog import ModelCatalogService
from app.core.model_registry import ModelRegistryError, ModelRegistryService


class ModelRouterError(RuntimeError):
    """Raised when no compatible model can be selected."""


@dataclass(frozen=True)
class ModelSelectionRequest:
    task_type: str
    subtask_type: str | None = None
    component: str | None = None
    input_format: str | None = None
    preferred_alias: str | None = None
    preferred_model_id: str | None = None


@dataclass(frozen=True)
class ModelSelectionResult:
    model_version_id: str | None
    legacy_model_id: str
    model_name: str | None
    entrypoint: str
    model_dir: str
    selection_reason: str
    model_alias: str | None = None


class ModelRouterService:
    def __init__(
        self,
        database_path: Path,
        littlemodel_root: Path,
        *,
        catalog_enabled: bool = True,
        fallback_to_v1: bool = True,
        default_alias: str = "default",
    ):
        self.catalog = ModelCatalogService(database_path)
        self.registry = ModelRegistryService(littlemodel_root)
        self.catalog_enabled = catalog_enabled
        self.fallback_to_v1 = fallback_to_v1
        self.default_alias = default_alias

    def select_model(self, request: ModelSelectionRequest) -> ModelSelectionResult:
        if self.catalog_enabled:
            if request.preferred_model_id:
                match = self.catalog.get_version_by_legacy_model_id(request.preferred_model_id)
                if match is not None:
                    return self._from_catalog_row(match, selection_reason="preferred_model_id", alias_name=None)

            if request.preferred_alias:
                match = self.catalog.get_version_by_task_and_alias(request.task_type, request.preferred_alias)
                if match is not None:
                    return self._from_catalog_row(
                        match,
                        selection_reason=f"preferred_alias:{request.preferred_alias}",
                        alias_name=request.preferred_alias,
                    )

            match = self.catalog.get_version_by_task_and_alias(request.task_type, self.default_alias)
            if match is not None:
                return self._from_catalog_row(
                    match,
                    selection_reason=f"task_type_default_alias:{self.default_alias}",
                    alias_name=self.default_alias,
                )

        if not self.fallback_to_v1:
            raise ModelRouterError(f"No catalog model matched task_type '{request.task_type}'.")

        try:
            model_entry = self.registry.get_active_model(request.task_type)
        except ModelRegistryError as exc:
            raise ModelRouterError(str(exc)) from exc

        return ModelSelectionResult(
            model_version_id=None,
            legacy_model_id=model_entry["model_id"],
            model_name=model_entry.get("model_name"),
            entrypoint=model_entry["entrypoint"],
            model_dir=model_entry["model_dir"],
            selection_reason="legacy_registry_active_model",
            model_alias=None,
        )

    def _from_catalog_row(self, row: dict[str, object], *, selection_reason: str, alias_name: str | None) -> ModelSelectionResult:
        return ModelSelectionResult(
            model_version_id=str(row["model_version_id"]),
            legacy_model_id=str(row["legacy_model_id"]),
            model_name=str(row["display_name"]) if row.get("display_name") is not None else None,
            entrypoint=str(row["entrypoint"]),
            model_dir=str(row["model_dir"]),
            selection_reason=selection_reason,
            model_alias=alias_name,
        )
