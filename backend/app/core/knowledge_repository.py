from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.db.database import Database


class KnowledgeRepositoryError(RuntimeError):
    """Raised when knowledge persistence operations fail."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class KnowledgeDocumentRecord:
    document_id: str
    source_type: str
    source_path: str
    title: str
    task_type: str | None = None
    subtask_type: str | None = None
    component: str | None = None
    model_family_id: str | None = None
    model_version_id: str | None = None
    language: str | None = "zh"
    status: str = "ready"
    checksum: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utcnow)
    updated_at: str = field(default_factory=_utcnow)


@dataclass
class KnowledgeChunkRecord:
    chunk_id: str
    document_id: str
    chunk_index: int
    content: str
    summary: str | None = None
    tokens_estimate: int | None = None
    embedding_model: str | None = None
    vector_store_id: str | None = None
    keywords: list[str] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utcnow)


class KnowledgeRepository:
    def __init__(self, database_path: Path):
        self.database = Database(database_path)
        self.database.initialize()

    def upsert_document(self, record: KnowledgeDocumentRecord) -> None:
        record.updated_at = _utcnow()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO knowledge_documents (
                    document_id,
                    source_type,
                    source_path,
                    title,
                    task_type,
                    subtask_type,
                    component,
                    model_family_id,
                    model_version_id,
                    language,
                    status,
                    checksum,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    source_type = excluded.source_type,
                    source_path = excluded.source_path,
                    title = excluded.title,
                    task_type = excluded.task_type,
                    subtask_type = excluded.subtask_type,
                    component = excluded.component,
                    model_family_id = excluded.model_family_id,
                    model_version_id = excluded.model_version_id,
                    language = excluded.language,
                    status = excluded.status,
                    checksum = excluded.checksum,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    record.document_id,
                    record.source_type,
                    record.source_path,
                    record.title,
                    record.task_type,
                    record.subtask_type,
                    record.component,
                    record.model_family_id,
                    record.model_version_id,
                    record.language,
                    record.status,
                    record.checksum,
                    json.dumps(record.metadata, ensure_ascii=False),
                    record.created_at,
                    record.updated_at,
                ),
            )

    def replace_chunks(self, document_id: str, chunks: list[KnowledgeChunkRecord]) -> None:
        with self.database.connect() as connection:
            connection.execute("DELETE FROM knowledge_chunks WHERE document_id = ?", (document_id,))
            for chunk in chunks:
                connection.execute(
                    """
                    INSERT INTO knowledge_chunks (
                        chunk_id,
                        document_id,
                        chunk_index,
                        content,
                        summary,
                        tokens_estimate,
                        embedding_model,
                        vector_store_id,
                        keywords_json,
                        citations_json,
                        metadata_json,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.chunk_id,
                        chunk.document_id,
                        chunk.chunk_index,
                        chunk.content,
                        chunk.summary,
                        chunk.tokens_estimate,
                        chunk.embedding_model,
                        chunk.vector_store_id,
                        json.dumps(chunk.keywords, ensure_ascii=False),
                        json.dumps(chunk.citations, ensure_ascii=False),
                        json.dumps(chunk.metadata, ensure_ascii=False),
                        chunk.created_at,
                    ),
                )

    def start_ingestion_run(self, source_scope: str) -> str:
        ingestion_run_id = uuid4().hex
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO knowledge_ingestion_runs (
                    ingestion_run_id,
                    status,
                    source_scope,
                    discovered_count,
                    processed_count,
                    failed_count,
                    details_json,
                    started_at,
                    finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ingestion_run_id,
                    "running",
                    source_scope,
                    0,
                    0,
                    0,
                    json.dumps({}, ensure_ascii=False),
                    _utcnow(),
                    None,
                ),
            )
        return ingestion_run_id

    def finish_ingestion_run(
        self,
        ingestion_run_id: str,
        *,
        status: str,
        discovered_count: int,
        processed_count: int,
        failed_count: int,
        details: dict[str, Any],
    ) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE knowledge_ingestion_runs
                SET status = ?,
                    discovered_count = ?,
                    processed_count = ?,
                    failed_count = ?,
                    details_json = ?,
                    finished_at = ?
                WHERE ingestion_run_id = ?
                """,
                (
                    status,
                    discovered_count,
                    processed_count,
                    failed_count,
                    json.dumps(details, ensure_ascii=False),
                    _utcnow(),
                    ingestion_run_id,
                ),
            )

    def list_documents(self) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM knowledge_documents
                ORDER BY updated_at DESC, document_id ASC
                """
            ).fetchall()
        return [self._decode_document_row(dict(row)) for row in rows]

    def list_chunks(
        self,
        *,
        document_id: str | None = None,
        task_type: str | None = None,
        component: str | None = None,
        source_type: str | None = None,
        model_family_id: str | None = None,
        model_version_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT
                c.chunk_id,
                c.document_id,
                c.chunk_index,
                c.content,
                c.summary,
                c.tokens_estimate,
                c.embedding_model,
                c.vector_store_id,
                c.keywords_json,
                c.citations_json,
                c.metadata_json,
                c.created_at,
                d.title,
                d.source_path,
                d.source_type,
                d.task_type,
                d.component,
                d.model_family_id,
                d.model_version_id
            FROM knowledge_chunks c
            JOIN knowledge_documents d ON d.document_id = c.document_id
        """
        conditions: list[str] = []
        params: list[Any] = []
        if document_id:
            conditions.append("c.document_id = ?")
            params.append(document_id)
        if task_type:
            conditions.append("d.task_type = ?")
            params.append(task_type)
        if component:
            conditions.append("d.component = ?")
            params.append(component)
        if source_type:
            conditions.append("d.source_type = ?")
            params.append(source_type)
        if model_family_id:
            conditions.append("d.model_family_id = ?")
            params.append(model_family_id)
        if model_version_id:
            conditions.append("d.model_version_id = ?")
            params.append(model_version_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY d.updated_at DESC, c.chunk_index ASC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        with self.database.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._decode_chunk_row(dict(row)) for row in rows]

    def list_ingestion_runs(self) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM knowledge_ingestion_runs
                ORDER BY started_at DESC, ingestion_run_id DESC
                """
            ).fetchall()
        runs: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["details"] = self._loads(payload.pop("details_json"), default={})
            runs.append(payload)
        return runs

    def update_chunk_vector_metadata(self, updates: list[dict[str, Any]]) -> None:
        if not updates:
            return
        with self.database.connect() as connection:
            connection.executemany(
                """
                UPDATE knowledge_chunks
                SET embedding_model = ?,
                    vector_store_id = ?
                WHERE chunk_id = ?
                """,
                [
                    (
                        item.get("embedding_model"),
                        item.get("vector_store_id"),
                        item["chunk_id"],
                    )
                    for item in updates
                ],
            )

    def get_index_stats(self) -> dict[str, Any]:
        with self.database.connect() as connection:
            totals_row = connection.execute(
                """
                SELECT
                    COUNT(*) AS total_chunks,
                    SUM(CASE WHEN vector_store_id IS NOT NULL AND vector_store_id != '' THEN 1 ELSE 0 END) AS indexed_chunks
                FROM knowledge_chunks
                """
            ).fetchone()
            models = connection.execute(
                """
                SELECT DISTINCT embedding_model
                FROM knowledge_chunks
                WHERE embedding_model IS NOT NULL AND embedding_model != ''
                ORDER BY embedding_model ASC
                """
            ).fetchall()
            document_count = connection.execute("SELECT COUNT(*) AS total_documents FROM knowledge_documents").fetchone()
        return {
            "document_count": int(document_count["total_documents"] or 0),
            "chunk_count": int(totals_row["total_chunks"] or 0),
            "indexed_chunk_count": int(totals_row["indexed_chunks"] or 0),
            "embedding_models": [str(row["embedding_model"]) for row in models],
        }

    def record_retrieval_event(
        self,
        *,
        case_id: str | None,
        query_text: str,
        task_type: str | None,
        top_k: int,
        filters: dict[str, Any],
        results: list[dict[str, Any]],
    ) -> str:
        retrieval_event_id = uuid4().hex
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO retrieval_events (
                    retrieval_event_id,
                    case_id,
                    query_text,
                    task_type,
                    top_k,
                    filters_json,
                    results_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    retrieval_event_id,
                    case_id,
                    query_text,
                    task_type,
                    top_k,
                    json.dumps(filters, ensure_ascii=False),
                    json.dumps(results, ensure_ascii=False),
                    _utcnow(),
                ),
            )
        return retrieval_event_id

    def _decode_document_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["metadata"] = self._loads(row.pop("metadata_json"), default={})
        return row

    def _decode_chunk_row(self, row: dict[str, Any]) -> dict[str, Any]:
        row["keywords"] = self._loads(row.pop("keywords_json"), default=[])
        row["citations"] = self._loads(row.pop("citations_json"), default=[])
        row["metadata"] = self._loads(row.pop("metadata_json"), default={})
        return row

    def _loads(self, raw: Any, *, default: Any) -> Any:
        if raw in (None, ""):
            return default
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise KnowledgeRepositoryError(f"Failed to decode repository JSON payload: {exc}") from exc
