from __future__ import annotations

from typing import Any

from app.core.case_store import CaseStoreError, CaseStoreService
from app.core.settings import Settings


class DiagnosisAgent:
    agent_name = "diagnosis_agent"

    def __init__(self, settings: Settings):
        self.case_store = CaseStoreService(settings.database_path)

    def prepare_case(self, case_id: str) -> dict[str, Any]:
        try:
            case = self.case_store.get_case_detail(case_id)
        except CaseStoreError as exc:
            raise RuntimeError(str(exc)) from exc
        return {
            "case_id": case_id,
            "task_type": case.get("task_type"),
            "model_id": case.get("model_id"),
            "risk_level": case.get("risk_level"),
            "status": "ready",
        }
