from __future__ import annotations

from app.core.agent_service import AgentService
from app.core.settings import Settings


class RetrievalAgent:
    agent_name = "retrieval_agent"

    def __init__(self, settings: Settings):
        self.service = AgentService(settings)

    def answer(
        self,
        case_id: str,
        question: str,
        session_id: str | None = None,
        *,
        run_id: str | None = None,
    ) -> dict[str, object]:
        return self.service.answer(case_id, question, session_id, run_id=run_id)
