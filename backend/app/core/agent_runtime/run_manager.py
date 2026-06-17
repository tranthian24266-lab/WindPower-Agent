from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.db.database import Database
from app.core.telemetry_service import TelemetryService


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunManager:
    def __init__(self, database_path: Path):
        self.database = Database(database_path)
        self.database.initialize()

    def create_run(
        self,
        *,
        run_type: str,
        case_id: str | None = None,
        session_id: str | None = None,
        input_payload: dict[str, Any] | None = None,
        triggered_by: str | None = None,
        trace_id: str | None = None,
    ) -> str:
        run_id = uuid4().hex
        trace_id = trace_id or TelemetryService.new_trace_id()
        now = _utcnow()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO agent_runs (
                    run_id,
                    run_type,
                    case_id,
                    session_id,
                    status,
                    current_step,
                    input_json,
                    output_json,
                    error_json,
                    started_at,
                    updated_at,
                    finished_at,
                    triggered_by,
                    trace_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    run_type,
                    case_id,
                    session_id,
                    "queued",
                    None,
                    self._dump_json(input_payload),
                    None,
                    None,
                    now,
                    now,
                    None,
                    triggered_by,
                    trace_id,
                ),
            )
        return run_id

    def mark_running(self, run_id: str, *, current_step: str | None = None) -> None:
        self._update_run(
            run_id,
            status="running",
            current_step=current_step,
            finished_at=None,
        )

    def complete_run(self, run_id: str, *, output_payload: dict[str, Any] | None = None, current_step: str | None = None) -> None:
        self._update_run(
            run_id,
            status="succeeded",
            current_step=current_step,
            output_json=self._dump_json(output_payload),
            error_json=None,
            finished_at=_utcnow(),
        )

    def mark_waiting_review(
        self,
        run_id: str,
        *,
        output_payload: dict[str, Any] | None = None,
        review_payload: dict[str, Any] | None = None,
        current_step: str | None = None,
    ) -> None:
        self._update_run(
            run_id,
            status="waiting_review",
            current_step=current_step,
            output_json=self._dump_json(output_payload),
            error_json=self._dump_json(review_payload),
            finished_at=None,
        )

    def fail_run(self, run_id: str, *, error_payload: dict[str, Any], current_step: str | None = None) -> None:
        self._update_run(
            run_id,
            status="failed",
            current_step=current_step,
            error_json=self._dump_json(error_payload),
            finished_at=_utcnow(),
        )

    def start_step(
        self,
        *,
        run_id: str,
        step_name: str,
        step_type: str,
        input_payload: dict[str, Any] | None = None,
    ) -> str:
        step_id = uuid4().hex
        now = _utcnow()
        with self.database.connect() as connection:
            sequence_no = (
                connection.execute(
                    "SELECT COALESCE(MAX(sequence_no), 0) + 1 FROM agent_run_steps WHERE run_id = ?",
                    (run_id,),
                ).fetchone()[0]
            )
            connection.execute(
                """
                INSERT INTO agent_run_steps (
                    step_id,
                    run_id,
                    step_name,
                    step_type,
                    status,
                    input_json,
                    output_json,
                    error_json,
                    duration_ms,
                    sequence_no,
                    started_at,
                    finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    step_id,
                    run_id,
                    step_name,
                    step_type,
                    "running",
                    self._dump_json(input_payload),
                    None,
                    None,
                    None,
                    sequence_no,
                    now,
                    None,
                ),
            )
        return step_id

    def complete_step(self, step_id: str, *, output_payload: dict[str, Any] | None = None, duration_ms: int | None = None) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE agent_run_steps
                SET status = ?, output_json = ?, error_json = ?, duration_ms = ?, finished_at = ?
                WHERE step_id = ?
                """,
                ("succeeded", self._dump_json(output_payload), None, duration_ms, _utcnow(), step_id),
            )

    def fail_step(self, step_id: str, *, error_payload: dict[str, Any], duration_ms: int | None = None) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE agent_run_steps
                SET status = ?, error_json = ?, duration_ms = ?, finished_at = ?
                WHERE step_id = ?
                """,
                ("failed", self._dump_json(error_payload), duration_ms, _utcnow(), step_id),
            )

    def start_tool_call(
        self,
        *,
        run_id: str,
        step_id: str,
        tool_name: str,
        request_payload: dict[str, Any] | None = None,
        tool_version: str | None = None,
    ) -> str:
        tool_call_id = uuid4().hex
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO agent_tool_calls (
                    tool_call_id,
                    run_id,
                    step_id,
                    tool_name,
                    tool_version,
                    request_json,
                    response_json,
                    status,
                    duration_ms,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tool_call_id,
                    run_id,
                    step_id,
                    tool_name,
                    tool_version,
                    self._dump_json(request_payload),
                    None,
                    "running",
                    None,
                    _utcnow(),
                ),
            )
        return tool_call_id

    def complete_tool_call(self, tool_call_id: str, *, response_payload: dict[str, Any] | None = None, duration_ms: int | None = None) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE agent_tool_calls
                SET status = ?, response_json = ?, duration_ms = ?
                WHERE tool_call_id = ?
                """,
                ("succeeded", self._dump_json(response_payload), duration_ms, tool_call_id),
            )

    def fail_tool_call(self, tool_call_id: str, *, error_payload: dict[str, Any], duration_ms: int | None = None) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE agent_tool_calls
                SET status = ?, response_json = ?, duration_ms = ?
                WHERE tool_call_id = ?
                """,
                ("failed", self._dump_json(error_payload), duration_ms, tool_call_id),
            )

    def list_runs(
        self,
        *,
        case_id: str | None = None,
        run_type: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT
                run_id,
                run_type,
                case_id,
                session_id,
                status,
                current_step,
                started_at,
                updated_at,
                finished_at,
                triggered_by
                ,
                trace_id
            FROM agent_runs
        """
        conditions: list[str] = []
        params: list[Any] = []
        if case_id:
            conditions.append("case_id = ?")
            params.append(case_id)
        if run_type:
            conditions.append("run_type = ?")
            params.append(run_type)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)

        with self.database.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_run_detail(self, run_id: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            run_row = connection.execute("SELECT * FROM agent_runs WHERE run_id = ?", (run_id,)).fetchone()
            if run_row is None:
                return None
            queue_row = connection.execute("SELECT * FROM agent_run_queue WHERE run_id = ?", (run_id,)).fetchone()
            step_rows = connection.execute(
                "SELECT * FROM agent_run_steps WHERE run_id = ? ORDER BY sequence_no ASC, started_at ASC",
                (run_id,),
            ).fetchall()
            tool_rows = connection.execute(
                "SELECT * FROM agent_tool_calls WHERE run_id = ? ORDER BY created_at ASC",
                (run_id,),
            ).fetchall()
            review_rows = connection.execute(
                """
                SELECT review_task_id, review_type, status, priority, reason_code, summary, requested_at, updated_at, decided_at
                FROM agent_review_tasks
                WHERE run_id = ?
                ORDER BY requested_at DESC
                """,
                (run_id,),
            ).fetchall()

        tools_by_step: dict[str, list[dict[str, Any]]] = {}
        for row in tool_rows:
            payload = self._deserialize_row(dict(row), json_fields=("request_json", "response_json"))
            tools_by_step.setdefault(str(payload["step_id"]), []).append(payload)

        run_payload = self._deserialize_row(
            dict(run_row),
            json_fields=("input_json", "output_json", "error_json"),
        )
        if queue_row is not None:
            run_payload["job"] = self._deserialize_row(
                dict(queue_row),
                json_fields=("payload_json", "last_error_json"),
            )
        steps: list[dict[str, Any]] = []
        for row in step_rows:
            step_payload = self._deserialize_row(
                dict(row),
                json_fields=("input_json", "output_json", "error_json"),
            )
            step_payload["tool_calls"] = tools_by_step.get(str(step_payload["step_id"]), [])
            steps.append(step_payload)

        run_payload["steps"] = steps
        run_payload["step_count"] = len(steps)
        run_payload["tool_call_count"] = sum(len(step["tool_calls"]) for step in steps)
        run_payload["review_tasks"] = [dict(row) for row in review_rows]
        return run_payload

    def enqueue_job(
        self,
        *,
        run_id: str,
        job_type: str,
        payload: dict[str, Any],
        max_attempts: int = 1,
    ) -> str:
        job_id = uuid4().hex
        now = _utcnow()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO agent_run_queue (
                    job_id,
                    run_id,
                    job_type,
                    payload_json,
                    status,
                    attempt_count,
                    max_attempts,
                    available_at,
                    lease_expires_at,
                    worker_id,
                    last_error_json,
                    created_at,
                    updated_at,
                    finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    run_id,
                    job_type,
                    self._dump_json(payload) or "{}",
                    "queued",
                    0,
                    max_attempts,
                    now,
                    None,
                    None,
                    None,
                    now,
                    now,
                    None,
                ),
            )
        return job_id

    def claim_next_job(self, *, worker_id: str, lease_seconds: int) -> dict[str, Any] | None:
        now = _utcnow()
        lease_expires_at = self._offset_utcnow(max(lease_seconds, 1))
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT *
                FROM agent_run_queue
                WHERE status = 'queued' AND available_at <= ?
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (now,),
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            job_id = str(row["job_id"])
            connection.execute(
                """
                UPDATE agent_run_queue
                SET status = 'running',
                    attempt_count = attempt_count + 1,
                    lease_expires_at = ?,
                    worker_id = ?,
                    updated_at = ?
                WHERE job_id = ?
                """,
                (lease_expires_at, worker_id, now, job_id),
            )
            connection.commit()
            claimed = connection.execute("SELECT * FROM agent_run_queue WHERE job_id = ?", (job_id,)).fetchone()
        return self._deserialize_row(dict(claimed), json_fields=("payload_json", "last_error_json")) if claimed else None

    def complete_job(self, job_id: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE agent_run_queue
                SET status = 'succeeded',
                    lease_expires_at = NULL,
                    updated_at = ?,
                    finished_at = ?
                WHERE job_id = ?
                """,
                (_utcnow(), _utcnow(), job_id),
            )

    def fail_job(self, job_id: str, *, error_payload: dict[str, Any]) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE agent_run_queue
                SET status = 'failed',
                    lease_expires_at = NULL,
                    last_error_json = ?,
                    updated_at = ?,
                    finished_at = ?
                WHERE job_id = ?
                """,
                (self._dump_json(error_payload), _utcnow(), _utcnow(), job_id),
            )

    def cancel_run(self, run_id: str) -> bool:
        with self.database.connect() as connection:
            row = connection.execute("SELECT status FROM agent_runs WHERE run_id = ?", (run_id,)).fetchone()
            if row is None or str(row["status"]) != "queued":
                return False
            connection.execute(
                """
                UPDATE agent_runs
                SET status = 'cancelled', updated_at = ?, finished_at = ?
                WHERE run_id = ?
                """,
                (_utcnow(), _utcnow(), run_id),
            )
            connection.execute(
                """
                UPDATE agent_run_queue
                SET status = 'cancelled', updated_at = ?, finished_at = ?
                WHERE run_id = ? AND status = 'queued'
                """,
                (_utcnow(), _utcnow(), run_id),
            )
        return True

    def resume_run(self, run_id: str) -> bool:
        with self.database.connect() as connection:
            row = connection.execute("SELECT status FROM agent_runs WHERE run_id = ?", (run_id,)).fetchone()
            if row is None or str(row["status"]) not in {"failed", "cancelled"}:
                return False
            job_row = connection.execute("SELECT status FROM agent_run_queue WHERE run_id = ?", (run_id,)).fetchone()
            if job_row is None or str(job_row["status"]) not in {"failed", "cancelled"}:
                return False
            now = _utcnow()
            connection.execute(
                """
                UPDATE agent_runs
                SET status = 'queued',
                    current_step = NULL,
                    error_json = NULL,
                    finished_at = NULL,
                    updated_at = ?
                WHERE run_id = ?
                """,
                (now, run_id),
            )
            connection.execute(
                """
                UPDATE agent_run_queue
                SET status = 'queued',
                    lease_expires_at = NULL,
                    worker_id = NULL,
                    last_error_json = NULL,
                    updated_at = ?,
                    finished_at = NULL
                WHERE run_id = ?
                """,
                (now, run_id),
            )
        return True

    def fail_stale_jobs(self, *, stale_timeout_seconds: int) -> int:
        stale_before = self._offset_utcnow(0)
        error_payload = {"type": "WorkerTimeout", "message": "Worker lease expired before the run completed."}
        with self.database.connect() as connection:
            stale_rows = connection.execute(
                """
                SELECT run_id, job_id
                FROM agent_run_queue
                WHERE status = 'running' AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?
                """,
                (stale_before,),
            ).fetchall()
            for row in stale_rows:
                connection.execute(
                    """
                    UPDATE agent_run_queue
                    SET status = 'failed',
                        last_error_json = ?,
                        lease_expires_at = NULL,
                        updated_at = ?,
                        finished_at = ?
                    WHERE job_id = ?
                    """,
                    (self._dump_json(error_payload), _utcnow(), _utcnow(), str(row["job_id"])),
                )
                connection.execute(
                    """
                    UPDATE agent_runs
                    SET status = 'failed',
                        error_json = ?,
                        updated_at = ?,
                        finished_at = ?
                    WHERE run_id = ? AND status = 'running'
                    """,
                    (self._dump_json(error_payload), _utcnow(), _utcnow(), str(row["run_id"])),
                )
        return len(stale_rows)

    def _update_run(
        self,
        run_id: str,
        *,
        status: str,
        current_step: str | None = None,
        output_json: str | None = None,
        error_json: str | None = None,
        finished_at: str | None = None,
    ) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE agent_runs
                SET status = ?,
                    current_step = ?,
                    output_json = COALESCE(?, output_json),
                    error_json = ?,
                    updated_at = ?,
                    finished_at = ?
                WHERE run_id = ?
                """,
                (status, current_step, output_json, error_json, _utcnow(), finished_at, run_id),
            )

    def _dump_json(self, payload: Any) -> str | None:
        if payload is None:
            return None
        return json.dumps(payload, ensure_ascii=False)

    def _offset_utcnow(self, seconds: int) -> str:
        return datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() + seconds, tz=timezone.utc).isoformat()

    def _deserialize_row(self, row: dict[str, Any], *, json_fields: tuple[str, ...]) -> dict[str, Any]:
        for field in json_fields:
            value = row.get(field)
            if value is None:
                row[field.removesuffix("_json")] = None
                row.pop(field, None)
                continue
            try:
                row[field.removesuffix("_json")] = json.loads(value)
            except json.JSONDecodeError:
                row[field.removesuffix("_json")] = {"raw": value}
            row.pop(field, None)
        return row
