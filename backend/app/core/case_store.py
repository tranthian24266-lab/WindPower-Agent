from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from app.db.database import Database


class CaseStoreError(RuntimeError):
    """Raised when persisted case data cannot be accessed safely."""


class CaseStoreService:
    def __init__(self, database_path: Path):
        self.database = Database(database_path)
        self.database.initialize()

    def save_uploaded_file(self, payload: dict[str, Any]) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO uploaded_files (
                    file_id,
                    original_filename,
                    stored_path,
                    suffix,
                    content_type,
                    size_bytes,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_id) DO UPDATE SET
                    original_filename = excluded.original_filename,
                    stored_path = excluded.stored_path,
                    suffix = excluded.suffix,
                    content_type = excluded.content_type,
                    size_bytes = excluded.size_bytes,
                    created_at = excluded.created_at
                """,
                (
                    payload["file_id"],
                    payload["original_filename"],
                    payload["stored_path"],
                    payload["suffix"],
                    payload.get("content_type"),
                    payload["size_bytes"],
                    payload["created_at"],
                ),
            )

    def save_diagnosis_case(self, payload: dict[str, Any]) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO diagnosis_cases (
                    case_id,
                    file_id,
                    task_type,
                    model_id,
                    model_name,
                    model_version_id,
                    model_alias,
                    selection_reason,
                    status,
                    risk_level,
                    result_json_path,
                    output_dir,
                    created_at,
                    report_html_path,
                    report_pdf_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(case_id) DO UPDATE SET
                    file_id = excluded.file_id,
                    task_type = excluded.task_type,
                    model_id = excluded.model_id,
                    model_name = excluded.model_name,
                    model_version_id = excluded.model_version_id,
                    model_alias = excluded.model_alias,
                    selection_reason = excluded.selection_reason,
                    status = excluded.status,
                    risk_level = excluded.risk_level,
                    result_json_path = excluded.result_json_path,
                    output_dir = excluded.output_dir,
                    created_at = excluded.created_at,
                    report_html_path = excluded.report_html_path,
                    report_pdf_path = excluded.report_pdf_path
                """,
                (
                    payload["case_id"],
                    payload["file_id"],
                    payload["task_type"],
                    payload["model_id"],
                    payload.get("model_name"),
                    payload.get("model_version_id"),
                    payload.get("model_alias"),
                    payload.get("selection_reason"),
                    payload["status"],
                    payload.get("risk_level"),
                    payload["result_json_path"],
                    payload["output_dir"],
                    payload["created_at"],
                    payload.get("report_html_path"),
                    payload.get("report_pdf_path"),
                ),
            )

    def list_cases(self, task_type: str | None = None, risk_level: str | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT
                c.case_id,
                c.file_id,
                c.task_type,
                c.model_id,
                c.model_name,
                c.model_version_id,
                c.model_alias,
                c.selection_reason,
                c.status,
                c.risk_level,
                c.result_json_path,
                c.output_dir,
                c.created_at,
                c.report_html_path,
                f.original_filename,
                f.suffix
            FROM diagnosis_cases c
            LEFT JOIN uploaded_files f ON f.file_id = c.file_id
        """
        conditions: list[str] = []
        params: list[Any] = []
        if task_type:
            conditions.append("c.task_type = ?")
            params.append(task_type)
        if risk_level:
            conditions.append("c.risk_level = ?")
            params.append(risk_level)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY c.created_at DESC"

        with self.database.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_case_detail(self, case_id: str) -> dict[str, Any]:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    c.case_id,
                    c.file_id,
                    c.task_type,
                    c.model_id,
                    c.model_name,
                    c.model_version_id,
                    c.model_alias,
                    c.selection_reason,
                    c.status,
                    c.risk_level,
                    c.result_json_path,
                    c.output_dir,
                    c.created_at,
                    c.report_html_path,
                    c.report_pdf_path,
                    f.original_filename,
                    f.stored_path,
                    f.suffix,
                    f.content_type,
                    f.size_bytes
                FROM diagnosis_cases c
                LEFT JOIN uploaded_files f ON f.file_id = c.file_id
                WHERE c.case_id = ?
                """,
                (case_id,),
            ).fetchone()
        if row is None:
            raise CaseStoreError(f"Diagnosis case does not exist for case_id '{case_id}'.")

        payload = dict(row)
        result_json_path = Path(payload["result_json_path"])
        if not result_json_path.exists():
            raise CaseStoreError(f"Result file does not exist for case_id '{case_id}': {result_json_path}")

        try:
            result = json.loads(result_json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CaseStoreError(f"Failed to parse result.json for case_id '{case_id}': {exc}") from exc

        payload["result"] = result
        return payload

    def update_report_paths(self, case_id: str, report_html_path: str, report_pdf_path: str | None = None) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE diagnosis_cases
                SET report_html_path = ?, report_pdf_path = ?
                WHERE case_id = ?
                """,
                (report_html_path, report_pdf_path, case_id),
            )

    def create_chat_session(self, case_id: str, session_id: str | None = None) -> str:
        session_id = session_id or uuid4().hex
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO chat_sessions (session_id, case_id, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO NOTHING
                """,
                (session_id, case_id, datetime.now(timezone.utc).isoformat()),
            )
        return session_id

    def save_chat_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        citations: list[dict[str, Any]] | None = None,
        knowledge_mode: str | None = None,
        retrieval_event_id: str | None = None,
        message_metadata: dict[str, Any] | None = None,
    ) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO chat_messages (
                    message_id,
                    session_id,
                    role,
                    content,
                    created_at,
                    citations_json,
                    knowledge_mode,
                    retrieval_event_id,
                    message_metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid4().hex,
                    session_id,
                    role,
                    content,
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps(citations, ensure_ascii=False) if citations else None,
                    knowledge_mode,
                    retrieval_event_id,
                    json.dumps(message_metadata, ensure_ascii=False) if message_metadata else None,
                ),
            )

    def get_chat_history(self, case_id: str) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    s.session_id,
                    s.case_id,
                    m.role,
                    m.content,
                    m.created_at,
                    m.citations_json,
                    m.knowledge_mode,
                    m.retrieval_event_id,
                    m.message_metadata_json
                FROM chat_sessions s
                JOIN chat_messages m ON m.session_id = s.session_id
                WHERE s.case_id = ?
                ORDER BY m.created_at ASC
                """,
                (case_id,),
            ).fetchall()
        return [self._deserialize_chat_message(dict(row)) for row in rows]

    def _deserialize_chat_message(self, row: dict[str, Any]) -> dict[str, Any]:
        citations_json = row.pop("citations_json", None)
        metadata_json = row.pop("message_metadata_json", None)
        row["citations"] = self._load_json_value(citations_json, [])
        row["message_metadata"] = self._load_json_value(metadata_json, {})
        return row

    def _load_json_value(self, value: str | None, default: Any) -> Any:
        if not value:
            return default
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
