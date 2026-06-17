from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Any

from app.db.database import Database


@dataclass(frozen=True)
class ModelFamilyRecord:
    family_id: str
    family_code: str
    display_name: str
    task_type: str
    subtask_type: str | None
    component: str | None
    description: str | None
    owner: str | None
    tags_json: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ModelVersionRecord:
    model_version_id: str
    family_id: str
    legacy_model_id: str
    version: str
    status: str
    validation_status: str
    model_dir: str
    entrypoint: str
    framework: str | None
    runtime: str | None
    dataset: str | None
    paper_title: str | None
    input_format: str | None
    output_schema_json: str | None
    feature_names_json: str | None
    limitations_json: str | None
    priority: int
    capabilities_json: str | None
    metadata_json: str | None
    created_at: str
    updated_at: str
    last_validated_at: str | None


@dataclass(frozen=True)
class ModelAliasRecord:
    alias_id: str
    family_id: str
    alias_name: str
    model_version_id: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ModelRegistrySyncRunRecord:
    sync_run_id: str
    source_path: str
    status: str
    discovered_count: int
    upserted_count: int
    failed_count: int
    details_json: str | None
    started_at: str
    finished_at: str | None


@dataclass(frozen=True)
class ModelValidationRunRecord:
    validation_run_id: str
    model_version_id: str
    validation_type: str
    status: str
    summary: str | None
    details_json: str | None
    started_at: str
    finished_at: str | None


class ModelCatalogService:
    def __init__(self, database_path: Path):
        self.database = Database(database_path)
        self.database.initialize()

    def upsert_family(self, connection: sqlite3.Connection, family: ModelFamilyRecord) -> None:
        connection.execute(
            """
            INSERT INTO model_families (
                family_id,
                family_code,
                display_name,
                task_type,
                subtask_type,
                component,
                description,
                owner,
                tags_json,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(family_id) DO UPDATE SET
                family_code = excluded.family_code,
                display_name = excluded.display_name,
                task_type = excluded.task_type,
                subtask_type = excluded.subtask_type,
                component = excluded.component,
                description = excluded.description,
                owner = excluded.owner,
                tags_json = excluded.tags_json,
                updated_at = excluded.updated_at
            """,
            (
                family.family_id,
                family.family_code,
                family.display_name,
                family.task_type,
                family.subtask_type,
                family.component,
                family.description,
                family.owner,
                family.tags_json,
                family.created_at,
                family.updated_at,
            ),
        )

    def upsert_version(self, connection: sqlite3.Connection, version: ModelVersionRecord) -> None:
        connection.execute(
            """
            INSERT INTO model_versions (
                model_version_id,
                family_id,
                legacy_model_id,
                version,
                status,
                validation_status,
                model_dir,
                entrypoint,
                framework,
                runtime,
                dataset,
                paper_title,
                input_format,
                output_schema_json,
                feature_names_json,
                limitations_json,
                priority,
                capabilities_json,
                metadata_json,
                created_at,
                updated_at,
                last_validated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(model_version_id) DO UPDATE SET
                family_id = excluded.family_id,
                legacy_model_id = excluded.legacy_model_id,
                version = excluded.version,
                status = excluded.status,
                validation_status = excluded.validation_status,
                model_dir = excluded.model_dir,
                entrypoint = excluded.entrypoint,
                framework = excluded.framework,
                runtime = excluded.runtime,
                dataset = excluded.dataset,
                paper_title = excluded.paper_title,
                input_format = excluded.input_format,
                output_schema_json = excluded.output_schema_json,
                feature_names_json = excluded.feature_names_json,
                limitations_json = excluded.limitations_json,
                priority = excluded.priority,
                capabilities_json = excluded.capabilities_json,
                metadata_json = excluded.metadata_json,
                updated_at = excluded.updated_at,
                last_validated_at = excluded.last_validated_at
            """,
            (
                version.model_version_id,
                version.family_id,
                version.legacy_model_id,
                version.version,
                version.status,
                version.validation_status,
                version.model_dir,
                version.entrypoint,
                version.framework,
                version.runtime,
                version.dataset,
                version.paper_title,
                version.input_format,
                version.output_schema_json,
                version.feature_names_json,
                version.limitations_json,
                version.priority,
                version.capabilities_json,
                version.metadata_json,
                version.created_at,
                version.updated_at,
                version.last_validated_at,
            ),
        )

    def upsert_alias(self, connection: sqlite3.Connection, alias: ModelAliasRecord) -> None:
        connection.execute(
            """
            INSERT INTO model_aliases (
                alias_id,
                family_id,
                alias_name,
                model_version_id,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(family_id, alias_name) DO UPDATE SET
                alias_id = excluded.alias_id,
                model_version_id = excluded.model_version_id,
                updated_at = excluded.updated_at
            """,
            (
                alias.alias_id,
                alias.family_id,
                alias.alias_name,
                alias.model_version_id,
                alias.created_at,
                alias.updated_at,
            ),
        )

    def delete_alias(self, connection: sqlite3.Connection, family_id: str, alias_name: str) -> None:
        connection.execute(
            """
            DELETE FROM model_aliases
            WHERE family_id = ? AND alias_name = ?
            """,
            (family_id, alias_name),
        )

    def record_sync_run(self, connection: sqlite3.Connection, sync_run: ModelRegistrySyncRunRecord) -> None:
        connection.execute(
            """
            INSERT INTO model_registry_sync_runs (
                sync_run_id,
                source_path,
                status,
                discovered_count,
                upserted_count,
                failed_count,
                details_json,
                started_at,
                finished_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sync_run.sync_run_id,
                sync_run.source_path,
                sync_run.status,
                sync_run.discovered_count,
                sync_run.upserted_count,
                sync_run.failed_count,
                sync_run.details_json,
                sync_run.started_at,
                sync_run.finished_at,
            ),
        )

    def record_validation_run(self, connection: sqlite3.Connection, validation_run: ModelValidationRunRecord) -> None:
        connection.execute(
            """
            INSERT INTO model_validation_runs (
                validation_run_id,
                model_version_id,
                validation_type,
                status,
                summary,
                details_json,
                started_at,
                finished_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                validation_run.validation_run_id,
                validation_run.model_version_id,
                validation_run.validation_type,
                validation_run.status,
                validation_run.summary,
                validation_run.details_json,
                validation_run.started_at,
                validation_run.finished_at,
            ),
        )

    def update_model_version_validation(
        self,
        connection: sqlite3.Connection,
        model_version_id: str,
        *,
        validation_status: str,
        last_validated_at: str | None,
    ) -> None:
        connection.execute(
            """
            UPDATE model_versions
            SET validation_status = ?, last_validated_at = ?, updated_at = COALESCE(?, updated_at)
            WHERE model_version_id = ?
            """,
            (validation_status, last_validated_at, last_validated_at, model_version_id),
        )

    def assign_alias(
        self,
        connection: sqlite3.Connection,
        *,
        family_id: str,
        alias_name: str,
        model_version_id: str,
        created_at: str,
        updated_at: str,
        enforce_task_uniqueness: bool = True,
    ) -> None:
        family = self.get_family_detail(family_id)
        if family is None:
            raise ValueError(f"Model family does not exist: {family_id}")

        version = self.get_model_version_detail(model_version_id)
        if version is None:
            raise ValueError(f"Model version does not exist: {model_version_id}")
        if version["family_id"] != family_id:
            raise ValueError(f"Model version {model_version_id} does not belong to family {family_id}")

        if enforce_task_uniqueness:
            connection.execute(
                """
                DELETE FROM model_aliases
                WHERE alias_name = ?
                  AND family_id IN (
                      SELECT family_id
                      FROM model_families
                      WHERE task_type = ?
                  )
                """,
                (alias_name, family["task_type"]),
            )

        self.upsert_alias(
            connection,
            ModelAliasRecord(
                alias_id=f"alias::{family_id}::{alias_name}",
                family_id=family_id,
                alias_name=alias_name,
                model_version_id=model_version_id,
                created_at=created_at,
                updated_at=updated_at,
            ),
        )

    def get_version_by_legacy_model_id(self, legacy_model_id: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    mv.model_version_id,
                    mv.family_id,
                    mv.legacy_model_id,
                    mv.version,
                    mv.status,
                    mv.validation_status,
                    mv.model_dir,
                    mv.entrypoint,
                    mv.priority,
                    mv.last_validated_at,
                    mf.family_code,
                    mf.display_name,
                    mf.task_type,
                    mf.subtask_type,
                    mf.component
                FROM model_versions mv
                JOIN model_families mf ON mf.family_id = mv.family_id
                WHERE mv.legacy_model_id = ?
                """,
                (legacy_model_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def get_version_by_task_and_alias(self, task_type: str, alias_name: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    mv.model_version_id,
                    mv.family_id,
                    mv.legacy_model_id,
                    mv.version,
                    mv.status,
                    mv.validation_status,
                    mv.model_dir,
                    mv.entrypoint,
                    mv.priority,
                    mv.last_validated_at,
                    mf.family_code,
                    mf.display_name,
                    mf.task_type,
                    mf.subtask_type,
                    mf.component,
                    ma.alias_name
                FROM model_aliases ma
                JOIN model_versions mv ON mv.model_version_id = ma.model_version_id
                JOIN model_families mf ON mf.family_id = ma.family_id
                WHERE mf.task_type = ? AND ma.alias_name = ?
                ORDER BY mv.priority ASC, mf.family_code ASC
                LIMIT 1
                """,
                (task_type, alias_name),
            ).fetchone()
        return dict(row) if row is not None else None

    def list_families(self) -> list[dict[str, Any]]:
        return self._fetch_all("SELECT * FROM model_families ORDER BY family_code ASC")

    def list_versions(self) -> list[dict[str, Any]]:
        return self._fetch_all("SELECT * FROM model_versions ORDER BY legacy_model_id ASC")

    def list_aliases(self) -> list[dict[str, Any]]:
        return self._fetch_all("SELECT * FROM model_aliases ORDER BY family_id ASC, alias_name ASC")

    def list_sync_runs(self) -> list[dict[str, Any]]:
        return self._fetch_all("SELECT * FROM model_registry_sync_runs ORDER BY started_at ASC")

    def list_validation_runs(self, model_version_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM model_validation_runs"
        params: list[Any] = []
        if model_version_id is not None:
            query += " WHERE model_version_id = ?"
            params.append(model_version_id)
        query += " ORDER BY started_at DESC"
        with self.database.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._enrich_validation_run_row(dict(row)) for row in rows]

    def list_catalog_models(
        self,
        *,
        q: str | None = None,
        task_type: str | None = None,
        subtask_type: str | None = None,
        component: str | None = None,
        status: str | None = None,
        validation_status: str | None = None,
        alias: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "family_code",
        sort_order: str = "asc",
    ) -> dict[str, Any]:
        sort_columns = {
            "family_code": "mf.family_code",
            "display_name": "mf.display_name",
            "task_type": "mf.task_type",
            "status": "mv.status",
            "validation_status": "mv.validation_status",
            "updated_at": "mv.updated_at",
            "created_at": "mv.created_at",
            "priority": "mv.priority",
        }
        order_column = sort_columns.get(sort_by, "mf.family_code")
        order_direction = "DESC" if sort_order.lower() == "desc" else "ASC"
        offset = max(page - 1, 0) * page_size

        conditions: list[str] = []
        params: list[Any] = []

        if q:
            conditions.append("(mf.family_code LIKE ? OR mf.display_name LIKE ? OR COALESCE(mf.description, '') LIKE ?)")
            needle = f"%{q}%"
            params.extend([needle, needle, needle])
        if task_type:
            conditions.append("mf.task_type = ?")
            params.append(task_type)
        if subtask_type:
            conditions.append("COALESCE(mf.subtask_type, '') = ?")
            params.append(subtask_type)
        if component:
            conditions.append("COALESCE(mf.component, '') = ?")
            params.append(component)
        if status:
            conditions.append("mv.status = ?")
            params.append(status)
        if validation_status:
            conditions.append("mv.validation_status = ?")
            params.append(validation_status)
        if alias:
            conditions.append(
                """
                EXISTS (
                    SELECT 1
                    FROM model_aliases ma_filter
                    WHERE ma_filter.family_id = mf.family_id
                      AND ma_filter.alias_name = ?
                )
                """
            )
            params.append(alias)

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        count_query = f"""
            SELECT COUNT(*)
            FROM model_families mf
            JOIN model_versions mv ON mv.family_id = mf.family_id
            {where_clause}
        """
        data_query = f"""
            SELECT
                mf.family_id,
                mf.family_code,
                mf.display_name,
                mf.task_type,
                mf.subtask_type,
                mf.component,
                mf.description,
                mf.owner,
                mf.tags_json,
                mf.created_at,
                mf.updated_at,
                mv.model_version_id,
                mv.legacy_model_id,
                mv.version,
                mv.status,
                mv.validation_status,
                mv.model_dir,
                mv.entrypoint,
                mv.framework,
                mv.runtime,
                mv.dataset,
                mv.paper_title,
                mv.input_format,
                mv.output_schema_json,
                mv.feature_names_json,
                mv.limitations_json,
                mv.priority,
                mv.capabilities_json,
                mv.metadata_json,
                mv.last_validated_at
            FROM model_families mf
            JOIN model_versions mv ON mv.family_id = mf.family_id
            {where_clause}
            ORDER BY {order_column} {order_direction}, mf.family_code ASC
            LIMIT ? OFFSET ?
        """

        with self.database.connect() as connection:
            total = int(connection.execute(count_query, params).fetchone()[0])
            rows = connection.execute(data_query, [*params, page_size, offset]).fetchall()

        items = [self._enrich_family_row(dict(row)) for row in rows]
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "has_next": page * page_size < total,
        }

    def get_family_detail(self, family_id: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM model_families
                WHERE family_id = ?
                """,
                (family_id,),
            ).fetchone()
        if row is None:
            return None

        payload = dict(row)
        payload["tags"] = _parse_json_text(payload.pop("tags_json", None))
        payload["aliases"] = self._list_aliases_for_family(family_id)
        payload["versions_count"] = len(self.list_family_versions(family_id))
        return payload

    def list_family_versions(self, family_id: str) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM model_versions
                WHERE family_id = ?
                ORDER BY priority ASC, created_at DESC
                """,
                (family_id,),
            ).fetchall()
        return [self._enrich_version_row(dict(row)) for row in rows]

    def get_model_version_detail(self, model_version_id: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    mv.*,
                    mf.family_code,
                    mf.display_name,
                    mf.task_type,
                    mf.subtask_type,
                    mf.component
                FROM model_versions mv
                JOIN model_families mf ON mf.family_id = mv.family_id
                WHERE mv.model_version_id = ?
                """,
                (model_version_id,),
            ).fetchone()
        if row is None:
            return None

        payload = self._enrich_version_row(dict(row))
        payload["aliases"] = self._list_aliases_for_model_version(payload["family_id"], model_version_id)
        payload["validation_runs"] = self.list_validation_runs(model_version_id)
        return payload

    def list_candidates_for_task(self, task_type: str) -> list[dict[str, Any]]:
        payload = self.list_catalog_models(task_type=task_type, page=1, page_size=500)
        return payload["items"]

    def _fetch_all(self, query: str) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(query).fetchall()
        return [dict(row) for row in rows]

    def _enrich_family_row(self, row: dict[str, Any]) -> dict[str, Any]:
        family_id = str(row["family_id"])
        payload = {
            key: row[key]
            for key in (
                "family_id",
                "family_code",
                "display_name",
                "task_type",
                "subtask_type",
                "component",
                "description",
                "owner",
                "created_at",
                "updated_at",
            )
        }
        payload["tags"] = _parse_json_text(row.get("tags_json"))
        payload["aliases"] = self._list_aliases_for_family(family_id)
        payload["latest_version"] = self._enrich_version_row(row)
        return payload

    def _enrich_version_row(self, row: dict[str, Any]) -> dict[str, Any]:
        payload = dict(row)
        payload["input_format"] = _parse_json_text(payload.get("input_format"))
        payload["output_schema"] = _parse_json_text(payload.pop("output_schema_json", None))
        payload["feature_names"] = _parse_json_text(payload.pop("feature_names_json", None))
        payload["limitations"] = _parse_json_text(payload.pop("limitations_json", None))
        payload["capabilities"] = _parse_json_text(payload.pop("capabilities_json", None))
        payload["metadata"] = _parse_json_text(payload.pop("metadata_json", None))
        return payload

    def _enrich_validation_run_row(self, row: dict[str, Any]) -> dict[str, Any]:
        payload = dict(row)
        payload["details"] = _parse_json_text(payload.pop("details_json", None))
        return payload

    def _list_aliases_for_family(self, family_id: str) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT alias_id, family_id, alias_name, model_version_id, created_at, updated_at
                FROM model_aliases
                WHERE family_id = ?
                ORDER BY alias_name ASC
                """,
                (family_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _list_aliases_for_model_version(self, family_id: str, model_version_id: str) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT alias_id, family_id, alias_name, model_version_id, created_at, updated_at
                FROM model_aliases
                WHERE family_id = ? AND model_version_id = ?
                ORDER BY alias_name ASC
                """,
                (family_id, model_version_id),
            ).fetchall()
        return [dict(row) for row in rows]


def to_json_text(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _parse_json_text(value: str | None) -> Any:
    if not value:
        return None
    return json.loads(value)
