from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.auth import ActorContext
from app.core.settings import Settings
from app.db.database import Database


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuditService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.database = Database(settings.database_path)

    def record(
        self,
        *,
        actor: ActorContext,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        outcome: str = "success",
        details: dict[str, Any] | None = None,
        run_id: str | None = None,
        trace_id: str | None = None,
    ) -> str:
        if not self.settings.audit_enabled:
            return ""
        audit_log_id = uuid4().hex
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO agent_audit_logs (
                    audit_log_id,
                    actor_id,
                    actor_role,
                    action,
                    resource_type,
                    resource_id,
                    outcome,
                    run_id,
                    trace_id,
                    details_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit_log_id,
                    actor.actor_id,
                    actor.role,
                    action,
                    resource_type,
                    resource_id,
                    outcome,
                    run_id,
                    trace_id,
                    json.dumps(details or {}, ensure_ascii=False),
                    _utcnow(),
                ),
            )
        return audit_log_id

    def list_logs(
        self,
        *,
        limit: int = 100,
        action: str | None = None,
        resource_type: str | None = None,
    ) -> list[dict[str, Any]]:
        params: list[Any] = []
        conditions: list[str] = []
        if action:
            conditions.append("action = ?")
            params.append(action)
        if resource_type:
            conditions.append("resource_type = ?")
            params.append(resource_type)
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(int(limit))
        with self.database.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM agent_audit_logs
                {where_clause}
                ORDER BY created_at DESC, audit_log_id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        payload: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                item["details"] = json.loads(item.pop("details_json") or "{}")
            except json.JSONDecodeError:
                item["details"] = {}
            item["audit_id"] = item.pop("audit_log_id")
            item["role"] = item.pop("actor_role")
            payload.append(item)
        return payload

    def get_summary(self) -> dict[str, Any]:
        logs = self.list_logs(limit=200)
        by_action: dict[str, int] = {}
        by_role: dict[str, int] = {}
        for item in logs:
            by_action[item["action"]] = by_action.get(item["action"], 0) + 1
            role = str(item.get("role") or "unknown")
            by_role[role] = by_role.get(role, 0) + 1
        return {
            "status": "ok",
            "log_count": len(logs),
            "counts_by_action": by_action,
            "counts_by_role": by_role,
            "recent_logs": logs[:20],
        }
