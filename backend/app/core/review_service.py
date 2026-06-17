from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any
from uuid import uuid4

from app.core.agent_runtime.run_manager import RunManager
from app.core.settings import Settings
from app.db.database import Database


class ReviewServiceError(RuntimeError):
    """Raised when review workflow operations cannot be completed safely."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReviewService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.database = Database(settings.database_path)
        self.database.initialize()
        self.run_manager = RunManager(settings.database_path)

    def ensure_report_review_task(
        self,
        *,
        run_id: str | None,
        case_id: str | None,
        report_version_id: str,
        summary: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self.database.connect() as connection:
            existing = connection.execute(
                """
                SELECT *
                FROM agent_review_tasks
                WHERE report_version_id = ? AND status = 'pending'
                ORDER BY requested_at DESC
                LIMIT 1
                """,
                (report_version_id,),
            ).fetchone()
            if existing is not None:
                return self.get_task(str(existing["review_task_id"]))

            review_task_id = uuid4().hex
            now = _utcnow()
            connection.execute(
                """
                INSERT INTO agent_review_tasks (
                    review_task_id,
                    run_id,
                    case_id,
                    report_version_id,
                    review_type,
                    status,
                    priority,
                    reason_code,
                    summary,
                    metadata_json,
                    requested_at,
                    updated_at,
                    decided_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_task_id,
                    run_id,
                    case_id,
                    report_version_id,
                    "enhanced_report_publication",
                    "pending",
                    "high",
                    "guardrail_waiting_review",
                    summary,
                    self._dump_json(metadata) or "{}",
                    now,
                    now,
                    None,
                ),
            )
            self._insert_action(
                connection,
                review_task_id=review_task_id,
                action="created",
                actor="system",
                comment=summary,
                metadata=metadata,
            )
        return self.get_task(review_task_id)

    def finalize_report_run(
        self,
        *,
        run_id: str,
        case_id: str | None,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        report_status = str(result.get("report_status") or "ready")
        if report_status != "waiting_review":
            self.run_manager.complete_run(run_id, output_payload=result, current_step="enhanced_report.generate")
            return result

        guardrails = (result.get("generation_metadata") or {}).get("guardrails") or {}
        review_task = self.ensure_report_review_task(
            run_id=run_id,
            case_id=case_id,
            report_version_id=str(result["report_version_id"]),
            summary="Enhanced report is waiting for human review before publication.",
            metadata={
                "report_status": report_status,
                "guardrails": guardrails,
            },
        )
        result["review_task_id"] = review_task["review_task_id"]
        self.run_manager.mark_waiting_review(
            run_id,
            output_payload=result,
            review_payload={
                "type": "HumanReviewRequired",
                "review_task_id": review_task["review_task_id"],
                "guardrails": guardrails,
            },
            current_step="review.pending",
        )
        return result

    def list_tasks(
        self,
        *,
        status: str | None = None,
        review_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT *
            FROM agent_review_tasks
        """
        conditions: list[str] = []
        params: list[Any] = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if review_type:
            conditions.append("review_type = ?")
            params.append(review_type)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY requested_at DESC LIMIT ?"
        params.append(limit)
        with self.database.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._deserialize_task(dict(row)) for row in rows]

    def get_task(self, review_task_id: str) -> dict[str, Any]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM agent_review_tasks WHERE review_task_id = ? LIMIT 1",
                (review_task_id,),
            ).fetchone()
            if row is None:
                raise ReviewServiceError(f"Review task does not exist for review_task_id '{review_task_id}'.")
            action_rows = connection.execute(
                """
                SELECT *
                FROM agent_review_actions
                WHERE review_task_id = ?
                ORDER BY created_at ASC, review_action_id ASC
                """,
                (review_task_id,),
            ).fetchall()
        payload = self._deserialize_task(dict(row))
        payload["actions"] = [self._deserialize_action(dict(item)) for item in action_rows]
        return payload

    def approve(self, review_task_id: str, *, reviewer: str | None = None, comment: str | None = None) -> dict[str, Any]:
        return self._transition_task(
            review_task_id,
            target_status="approved",
            report_status="ready",
            action="approved",
            reviewer=reviewer,
            comment=comment,
        )

    def reject(self, review_task_id: str, *, reviewer: str | None = None, comment: str | None = None) -> dict[str, Any]:
        return self._transition_task(
            review_task_id,
            target_status="rejected",
            report_status="rejected",
            action="rejected",
            reviewer=reviewer,
            comment=comment,
        )

    def request_changes(
        self,
        review_task_id: str,
        *,
        reviewer: str | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]:
        return self._transition_task(
            review_task_id,
            target_status="changes_requested",
            report_status="changes_requested",
            action="changes_requested",
            reviewer=reviewer,
            comment=comment,
        )

    def _transition_task(
        self,
        review_task_id: str,
        *,
        target_status: str,
        report_status: str,
        action: str,
        reviewer: str | None,
        comment: str | None,
    ) -> dict[str, Any]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM agent_review_tasks WHERE review_task_id = ? LIMIT 1",
                (review_task_id,),
            ).fetchone()
            if row is None:
                raise ReviewServiceError(f"Review task does not exist for review_task_id '{review_task_id}'.")
            task = self._deserialize_task(dict(row))
            if task["status"] != "pending":
                raise ReviewServiceError(
                    f"Review task '{review_task_id}' cannot transition from status '{task['status']}'."
                )

            now = _utcnow()
            connection.execute(
                """
                UPDATE agent_review_tasks
                SET status = ?, updated_at = ?, decided_at = ?
                WHERE review_task_id = ?
                """,
                (target_status, now, now, review_task_id),
            )
            if task.get("report_version_id"):
                connection.execute(
                    """
                    UPDATE report_versions
                    SET status = ?, updated_at = ?
                    WHERE report_version_id = ?
                    """,
                    (report_status, now, task["report_version_id"]),
                )
            self._insert_action(
                connection,
                review_task_id=review_task_id,
                action=action,
                actor=reviewer or "reviewer",
                comment=comment,
                metadata={"target_status": target_status, "report_status": report_status},
            )

        if task.get("run_id"):
            if target_status == "approved":
                self.run_manager.complete_run(
                    str(task["run_id"]),
                    current_step="review.approved",
                )
            else:
                error_type = "ReviewRejected" if target_status == "rejected" else "ReviewChangesRequested"
                error_message = comment or f"Review task {review_task_id} ended with status '{target_status}'."
                self.run_manager.fail_run(
                    str(task["run_id"]),
                    error_payload={"type": error_type, "message": error_message},
                    current_step=f"review.{action}",
                )

        return self.get_task(review_task_id)

    def _insert_action(
        self,
        connection: Any,
        *,
        review_task_id: str,
        action: str,
        actor: str | None,
        comment: str | None,
        metadata: dict[str, Any] | None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO agent_review_actions (
                review_action_id,
                review_task_id,
                action,
                actor,
                comment,
                metadata_json,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid4().hex,
                review_task_id,
                action,
                actor,
                comment,
                self._dump_json(metadata) or "{}",
                _utcnow(),
            ),
        )

    def _dump_json(self, payload: dict[str, Any] | None) -> str | None:
        if payload is None:
            return None
        return json.dumps(payload, ensure_ascii=False)

    def _deserialize_task(self, row: dict[str, Any]) -> dict[str, Any]:
        metadata_json = row.pop("metadata_json", None)
        row["metadata"] = self._load_json(metadata_json)
        return row

    def _deserialize_action(self, row: dict[str, Any]) -> dict[str, Any]:
        metadata_json = row.pop("metadata_json", None)
        row["metadata"] = self._load_json(metadata_json)
        return row

    def _load_json(self, value: str | None) -> dict[str, Any] | None:
        if not value:
            return None
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {"raw": value}
        return parsed if isinstance(parsed, dict) else {"value": parsed}
