from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.settings import Settings


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class TelemetryService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def record(self, event_type: str, payload: dict[str, Any]) -> str | None:
        if not self.settings.observability_enabled:
            return None

        self.settings.telemetry_path.mkdir(parents=True, exist_ok=True)
        event_id = uuid4().hex
        record = {
            "event_id": event_id,
            "event_type": event_type,
            "created_at": _utcnow(),
            "payload": payload,
        }
        events_path = self.events_path
        with events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return event_id

    def record_trace_span(
        self,
        *,
        trace_id: str,
        span_id: str,
        parent_span_id: str | None,
        name: str,
        status: str,
        attributes: dict[str, Any] | None = None,
    ) -> str | None:
        return self.record(
            "trace_span",
            {
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id,
                "name": name,
                "status": status,
                "attributes": attributes or {},
            },
        )

    def list_events(
        self,
        *,
        event_type: str | None = None,
        trace_id: str | None = None,
        run_id: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        path = self.events_path
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event_type and payload.get("event_type") != event_type:
                continue
            event_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
            if trace_id and event_payload.get("trace_id") != trace_id:
                continue
            if run_id and event_payload.get("run_id") != run_id:
                continue
            rows.append(payload)
        return rows[-limit:]

    @staticmethod
    def new_trace_id() -> str:
        return uuid4().hex + uuid4().hex[:16]

    @staticmethod
    def new_span_id() -> str:
        return uuid4().hex[:16]

    @property
    def events_path(self) -> Path:
        return self.settings.telemetry_path / "events.jsonl"
