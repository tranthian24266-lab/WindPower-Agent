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
            current_family_ids = {self._family_id_for_entry(entry) for entry in models}
            current_model_version_ids = {f"model_version::{entry['model_id']}" for entry in models}

            with self.catalog.database.connect() as connection:
                for entry in models:
                    family = self._build_family_record(entry, started_at)
                    version = self._build_version_record(entry, family.family_id, started_at)
                    self.catalog.upsert_family(connection, family)
                    self.catalog.upsert_version(connection, version)
                    upserted_count += 1

                active_by_family = {
                    self._family_id_for_entry(entry): entry
                    for entry in models
                    if entry["status"] == "active"
                }
                for family_id in current_family_ids:
                    active_entry = active_by_family.get(family_id)
                    if active_entry is not None:
                        self.catalog.upsert_alias(
                            connection,
                            ModelAliasRecord(
                                alias_id=f"alias::{family_id}::{self.default_alias}",
                                family_id=family_id,
                                alias_name=self.default_alias,
                                model_version_id=f"model_version::{active_entry['model_id']}",
                                created_at=started_at,
                                updated_at=started_at,
                            ),
                        )
                    else:
                        self.catalog.delete_alias(connection, family_id, self.default_alias)

                self._delete_stale_legacy_registry_rows(
                    connection,
                    current_family_ids=current_family_ids,
                    current_model_version_ids=current_model_version_ids,
                )

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
        family_id = self._family_id_for_entry(entry)
        return ModelFamilyRecord(
            family_id=family_id,
            family_code=entry.get("family_code") or entry["model_id"],
            display_name=entry.get("model_name") or entry["model_id"],
            task_type=entry["task_type"],
            subtask_type=None,
            component=None,
            description=entry.get("description") or entry.get("readme_summary"),
            owner="legacy_registry_sync",
            tags_json=to_json_text([entry["task_type"], "legacy-registry"]),
            created_at=timestamp,
            updated_at=timestamp,
        )

    def _build_version_record(self, entry: dict[str, Any], family_id: str, timestamp: str) -> ModelVersionRecord:
        source_status = entry["status"]
        status_mapping = {
            "active": "production",
            "candidate": "candidate",
            "archived": "archived",
        }
        catalog_status = status_mapping.get(source_status, "draft")
        is_validated = source_status in status_mapping
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
            status=catalog_status,
            validation_status="passed" if is_validated else "pending",
            model_dir=entry["model_dir"],
            entrypoint=entry["entrypoint"],
            framework=entry.get("framework"),
            runtime=entry.get("runtime"),
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
            last_validated_at=timestamp if is_validated else None,
        )

    def _family_id_for_entry(self, entry: dict[str, Any]) -> str:
        return f"family::{entry.get('family_code') or entry['model_id']}"

    def _delete_stale_legacy_registry_rows(
        self,
        connection,
        *,
        current_family_ids: set[str],
        current_model_version_ids: set[str],
    ) -> None:
        version_rows = connection.execute(
            """
            SELECT mv.model_version_id
            FROM model_versions mv
            JOIN model_families mf ON mf.family_id = mv.family_id
            WHERE mf.owner = 'legacy_registry_sync'
            """
        ).fetchall()
        stale_model_version_ids = [
            str(row["model_version_id"])
            for row in version_rows
            if str(row["model_version_id"]) not in current_model_version_ids
        ]
        if stale_model_version_ids:
            version_placeholders = ", ".join("?" for _ in stale_model_version_ids)
            connection.execute(
                f"DELETE FROM model_aliases WHERE model_version_id IN ({version_placeholders})",
                stale_model_version_ids,
            )
            connection.execute(
                f"DELETE FROM model_validation_runs WHERE model_version_id IN ({version_placeholders})",
                stale_model_version_ids,
            )
            connection.execute(
                f"DELETE FROM model_versions WHERE model_version_id IN ({version_placeholders})",
                stale_model_version_ids,
            )

        rows = connection.execute(
            """
            SELECT family_id
            FROM model_families
            WHERE owner = 'legacy_registry_sync'
            """
        ).fetchall()
        stale_family_ids = [
            str(row["family_id"])
            for row in rows
            if str(row["family_id"]) not in current_family_ids
        ]
        if not stale_family_ids:
            return

        placeholders = ", ".join("?" for _ in stale_family_ids)
        connection.execute(
            f"DELETE FROM model_aliases WHERE family_id IN ({placeholders})",
            stale_family_ids,
        )
        connection.execute(
            f"DELETE FROM model_validation_runs WHERE model_version_id IN (SELECT model_version_id FROM model_versions WHERE family_id IN ({placeholders}))",
            stale_family_ids,
        )
        connection.execute(
            f"DELETE FROM model_versions WHERE family_id IN ({placeholders})",
            stale_family_ids,
        )
        connection.execute(
            f"DELETE FROM model_families WHERE family_id IN ({placeholders})",
            stale_family_ids,
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
