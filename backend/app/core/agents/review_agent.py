from __future__ import annotations

from app.core.review_service import ReviewService
from app.core.settings import Settings


class ReviewAgent:
    agent_name = "review_agent"

    def __init__(self, settings: Settings):
        self.service = ReviewService(settings)

    def finalize_report_run(self, *, run_id: str, case_id: str, result: dict[str, object]) -> dict[str, object]:
        return self.service.finalize_report_run(run_id=run_id, case_id=case_id, result=result)
