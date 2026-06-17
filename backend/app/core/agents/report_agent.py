from __future__ import annotations

from app.core.enhanced_report_service import EnhancedReportService
from app.core.settings import Settings


class ReportAgent:
    agent_name = "report_agent"

    def __init__(self, settings: Settings):
        self.service = EnhancedReportService(settings)

    def generate(self, case_id: str, *, run_id: str | None = None) -> dict[str, object]:
        return self.service.generate(case_id, run_id=run_id)
