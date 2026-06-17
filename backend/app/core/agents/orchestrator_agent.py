from __future__ import annotations

from typing import Any

from app.core.agent_runtime.run_manager import RunManager
from app.core.audit_service import AuditService
from app.core.auth import ActorContext
from app.core.agents.diagnosis_agent import DiagnosisAgent
from app.core.agents.report_agent import ReportAgent
from app.core.agents.retrieval_agent import RetrievalAgent
from app.core.agents.review_agent import ReviewAgent
from app.core.settings import Settings
from app.core.telemetry_service import TelemetryService


class OrchestratorAgent:
    agent_name = "orchestrator_agent"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.run_manager = RunManager(settings.database_path)
        self.telemetry = TelemetryService(settings)
        self.audit = AuditService(settings)
        self.diagnosis_agent = DiagnosisAgent(settings)
        self.retrieval_agent = RetrievalAgent(settings)
        self.report_agent = ReportAgent(settings)
        self.review_agent = ReviewAgent(settings)

    def run_chat_answer(
        self,
        *,
        run_id: str,
        case_id: str,
        question: str,
        session_id: str | None = None,
        actor: ActorContext | None = None,
    ) -> dict[str, object]:
        self._record_handoff(run_id=run_id, specialist=self.diagnosis_agent.agent_name, capability="prepare_case", actor=actor)
        self.diagnosis_agent.prepare_case(case_id)
        self._record_handoff(run_id=run_id, specialist=self.retrieval_agent.agent_name, capability="answer_case_question", actor=actor)
        result = self.retrieval_agent.answer(case_id, question, session_id, run_id=run_id)
        self._record_completion(run_id=run_id, workflow="chat_answer", actor=actor, result=result)
        return result

    def run_enhanced_report(
        self,
        *,
        run_id: str,
        case_id: str,
        actor: ActorContext | None = None,
    ) -> dict[str, object]:
        self._record_handoff(run_id=run_id, specialist=self.diagnosis_agent.agent_name, capability="prepare_case", actor=actor)
        self.diagnosis_agent.prepare_case(case_id)
        self._record_handoff(run_id=run_id, specialist=self.report_agent.agent_name, capability="generate_enhanced_report", actor=actor)
        result = self.report_agent.generate(case_id, run_id=run_id)
        self._record_handoff(run_id=run_id, specialist=self.review_agent.agent_name, capability="finalize_report_run", actor=actor)
        finalized = self.review_agent.finalize_report_run(run_id=run_id, case_id=case_id, result=result)
        self._record_completion(run_id=run_id, workflow="enhanced_report", actor=actor, result=finalized)
        return finalized

    def _record_handoff(
        self,
        *,
        run_id: str,
        specialist: str,
        capability: str,
        actor: ActorContext | None,
    ) -> None:
        trace_id = self._trace_id_for_run(run_id)
        payload = {
            "run_id": run_id,
            "trace_id": trace_id,
            "from_agent": self.agent_name,
            "to_agent": specialist,
            "capability": capability,
            "status": "delegated",
        }
        self.telemetry.record("agent_handoff", payload)
        if actor is not None:
            self.audit.record(
                actor=actor,
                action="agent.handoff",
                resource_type="agent_run",
                resource_id=run_id,
                run_id=run_id,
                trace_id=trace_id,
                details=payload,
            )

    def _record_completion(
        self,
        *,
        run_id: str,
        workflow: str,
        actor: ActorContext | None,
        result: dict[str, object],
    ) -> None:
        trace_id = self._trace_id_for_run(run_id)
        payload = {
            "run_id": run_id,
            "trace_id": trace_id,
            "agent_name": self.agent_name,
            "workflow": workflow,
            "status": str(result.get("status") or "ok"),
        }
        self.telemetry.record("agent_orchestration_summary", payload)
        if actor is not None:
            self.audit.record(
                actor=actor,
                action="agent.orchestration",
                resource_type="agent_run",
                resource_id=run_id,
                run_id=run_id,
                trace_id=trace_id,
                details=payload,
            )

    def _trace_id_for_run(self, run_id: str) -> str | None:
        detail = self.run_manager.get_run_detail(run_id) or {}
        trace_id = detail.get("trace_id")
        return str(trace_id) if trace_id else None
