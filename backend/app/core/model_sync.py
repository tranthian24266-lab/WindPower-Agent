from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.model_catalog import (
    ModelAliasRecord,
    ModelCatalogService,
    ModelFamilyRecord,
    ModelRegistrySyncRunRecord,
    ModelVersionRecord,
    to_json_text,
)
from app.core.model_registry import ModelRegistryError, ModelRegistryService


class ModelSyncError(RuntimeError):
    """Raised when the legacy registry cannot be synchronized safely."""


@dataclass(frozen=True)
class ModelSyncResult:
    sync_run_id: str
    source_path: str
    status: str
    discovered_count: int
    upserted_count: int
    failed_count: int
    details: dict[str, Any]
    started_at: str
    finished_at: str


class ModelSyncService:
    def __init__(self, database_path: Path, littlemodel_root: Path, default_alias: str = "default"):
        self.catalog = ModelCatalogService(database_path)
        self.registry = ModelRegistryService(littlemodel_root)
        self.default_alias = default_alias

    def sync_registry(self) -> ModelSyncResult:
        sync_run_id = uuid4().hex
        started_at = _utcnow()
        discovered_count = 0
        upserted_count = 0

        try:
            models = self.registry.list_models()
            discovered_count = len(models)
            self._assert_active_model_conflicts(models)

            with self.catalog.database.connect() as connection:
                for entry in models:
                    family = self._build_family_record(entry, started_at)
                    version = self._build_version_record(entry, family.family_id, started_at)
                    self.catalog.upsert_family(connection, family)
                    self.catalog.upsert_version(connection, version)
                    if entry["status"] == "active":
                        self.catalog.upsert_alias(
                            connection,
                            ModelAliasRecord(
                                alias_id=f"alias::{family.family_id}::{self.default_alias}",
                                family_id=family.family_id,
                                alias_name=self.default_alias,
                                model_version_id=version.model_version_id,
                                created_at=started_at,
                                updated_at=started_at,
                            ),
                        )
                    else:
                        self.catalog.delete_alias(connection, family.family_id, self.default_alias)
                    upserted_count += 1

                result = ModelSyncResult(
                    sync_run_id=sync_run_id,
                    source_path=str(self.registry.registry_path),
                    status="success",
                    discovered_count=discovered_count,
                    upserted_count=upserted_count,
                    failed_count=0,
                    details={"default_alias": self.default_alias},
                    started_at=started_at,
                    finished_at=_utcnow(),
                )
                self.catalog.record_sync_run(connection, self._as_sync_run_record(result))
            return result
        except (ModelRegistryError, ModelSyncError) as exc:
            result = ModelSyncResult(
                sync_run_id=sync_run_id,
                source_path=str(self.registry.registry_path),
                status="failed",
                discovered_count=discovered_count,
                upserted_count=upserted_count,
                failed_count=max(1, discovered_count - upserted_count),
                details={"error": str(exc)},
                started_at=started_at,
                finished_at=_utcnow(),
            )
            with self.catalog.database.connect() as connection:
                self.catalog.record_sync_run(connection, self._as_sync_run_record(result))
            raise ModelSyncError(str(exc)) from exc

    def _build_family_record(self, entry: dict[str, Any], timestamp: str) -> ModelFamilyRecord:
        family_id = f"family::{entry['model_id']}"
        return ModelFamilyRecord(
            family_id=family_id,
            family_code=entry["model_id"],
            display_name=entry.get("model_name") or entry["model_id"],
            task_type=entry["task_type"],
            subtask_type=None,
            component=None,
            description=entry.get("readme_summary"),
            owner="legacy_registry_sync",
            tags_json=to_json_text([entry["task_type"], "legacy-registry"]),
            created_at=timestamp,
            updated_at=timestamp,
        )

    def _build_version_record(self, entry: dict[str, Any], family_id: str, timestamp: str) -> ModelVersionRecord:
        is_active = entry["status"] == "active"
        metadata = {
            "readme_summary": entry.get("readme_summary"),
            "output_labels": entry.get("output_labels"),
            "threshold": entry.get("threshold"),
            "source_status": entry["status"],
        }
        return ModelVersionRecord(
            model_version_id=f"model_version::{entry['model_id']}",
            family_id=family_id,
            legacy_model_id=entry["model_id"],
            version=entry.get("version") or "unknown",
            status="production" if is_active else "draft",
            validation_status="passed" if is_active else "pending",
            model_dir=entry["model_dir"],
            entrypoint=entry["entrypoint"],
            framework=None,
            runtime=None,
            dataset=entry.get("dataset"),
            paper_title=entry.get("paper_title"),
            input_format=to_json_text(entry.get("input_format")),
            output_schema_json=to_json_text(entry.get("output_labels")),
            feature_names_json=to_json_text(entry.get("feature_names")),
            limitations_json=to_json_text(entry.get("limitations") or []),
            priority=100,
            capabilities_json=to_json_text({"task_type": entry["task_type"]}),
            metadata_json=to_json_text(metadata),
            created_at=timestamp,
            updated_at=timestamp,
            last_validated_at=timestamp if is_active else None,
        )

    def _assert_active_model_conflicts(self, models: list[dict[str, Any]]) -> None:
        active_by_task: dict[str, list[str]] = {}
        for entry in models:
            if entry["status"] != "active":
                continue
            active_by_task.setdefault(entry["task_type"], []).append(entry["model_id"])

        conflicts = {task_type: model_ids for task_type, model_ids in active_by_task.items() if len(model_ids) > 1}
        if conflicts:
            raise ModelSyncError(f"Multiple active models detected for task types: {conflicts}")

    def _as_sync_run_record(self, result: ModelSyncResult) -> ModelRegistrySyncRunRecord:
        return ModelRegistrySyncRunRecord(
            sync_run_id=result.sync_run_id,
            source_path=result.source_path,
            status=result.status,
            discovered_count=result.discovered_count,
            upserted_count=result.upserted_count,
            failed_count=result.failed_count,
            details_json=to_json_text(result.details),
            started_at=result.started_at,
            finished_at=result.finished_at,
        )


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()
