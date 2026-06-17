from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.agent_runtime.guardrails import ToolAccessDeniedError
from app.core.agent_runtime.run_manager import RunManager
from app.core.agent_runtime.step_executor import StepExecutor
from app.core.agent_runtime.tool_registry import ToolRegistry
from app.core.deepseek_client import DeepSeekChatResult
from app.core.settings import Settings
from app.main import create_app


LITTLEMODEL_ROOT = Path(r"C:\Users\luzian\Desktop\littlemodel")


def _create_client(tmp_path: Path, **overrides: object) -> TestClient:
    payload: dict[str, object] = {
        "backend_root": tmp_path,
        "littlemodel_root": LITTLEMODEL_ROOT,
        "knowledge_ingestion_enabled": True,
        "knowledge_rag_enabled": True,
        "chat_rag_enabled": True,
        "knowledge_case_ingestion_enabled": True,
        "enhanced_reports_enabled": True,
        "enhanced_report_llm_enabled": True,
        "deepseek_api_key": "test-key",
    }
    payload.update(overrides)
    settings = Settings(**payload)
    return TestClient(create_app(settings))


def _create_case(client: TestClient, path: Path) -> str:
    with path.open("rb") as handle:
        upload = client.post("/api/upload", files={"file": (path.name, handle)})
    file_id = upload.json()["file"]["file_id"]
    diagnose = client.post("/api/diagnose", json={"file_id": file_id, "task_type": "fault_diagnosis"})
    return diagnose.json()["case_id"]


def test_tool_registry_blocks_cross_run_type_tool_invocation(tmp_path: Path) -> None:
    settings = Settings(backend_root=tmp_path, littlemodel_root=LITTLEMODEL_ROOT)
    run_manager = RunManager(settings.database_path)
    run_id = run_manager.create_run(run_type="chat_answer", input_payload={"question": "test"})
    tool_registry = ToolRegistry()
    tool_registry.register(
        "enhanced_report.generate",
        lambda: {"status": "ok"},
        allowed_run_types=("enhanced_report",),
    )
    executor = StepExecutor(run_manager, tool_registry)

    with pytest.raises(ToolAccessDeniedError):
        executor.execute_tool(
            run_id=run_id,
            step_name="enhanced_report.generate",
            tool_name="enhanced_report.generate",
            request_payload={"case_id": "case-1"},
        )

    detail = run_manager.get_run_detail(run_id)
    assert detail is not None
    assert detail["steps"][0]["status"] == "failed"
    assert detail["steps"][0]["error"]["type"] == "ToolAccessDeniedError"


def test_high_risk_report_without_grounded_citations_enters_waiting_review(tmp_path: Path, monkeypatch) -> None:
    class FakeDeepSeekClient:
        def __init__(self, settings: Settings):
            self.settings = settings

        def create_chat_completion(self, **kwargs) -> DeepSeekChatResult:
            return DeepSeekChatResult(
                content="""
                {
                  "case_summary": {"title": "案例摘要", "content": "摘要", "confidence": 0.92, "evidence_refs": ["case_result"]},
                  "diagnosis_conclusion": {"title": "诊断结论", "content": "结论", "confidence": 0.9, "evidence_refs": ["case_result"]},
                  "risk_assessment": {"title": "风险评估", "content": "存在较高风险。", "confidence": 0.89, "evidence_refs": ["model_metadata"]},
                  "evidence_summary": {"title": "证据摘要", "content": "证据摘要", "confidence": 0.88, "evidence_refs": ["case_result"]},
                  "maintenance_actions": {"title": "维护建议", "content": "建议尽快停机检查。", "confidence": 0.87, "evidence_refs": ["model_metadata"]},
                  "applicability_and_limits": {"title": "适用边界", "content": "适用边界", "confidence": 0.86, "evidence_refs": ["model_metadata"]},
                  "similar_cases": [],
                  "appendix_metrics": [],
                  "citations": []
                }
                """,
                reasoning_content=None,
                raw_payload={},
                usage={},
            )

    monkeypatch.setattr("app.core.enhanced_report_llm.DeepSeekClient", FakeDeepSeekClient)

    client = _create_client(tmp_path)
    case_id = _create_case(client, LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy")

    from app.core.report_evidence_service import ReportEvidenceService

    original_collect = ReportEvidenceService.collect

    def force_high_risk(self: ReportEvidenceService, current_case_id: str) -> dict[str, object]:
        payload = original_collect(self, current_case_id)
        payload["case_context"]["risk_level"] = "critical"
        payload["case_context"]["result"]["risk_level"] = "critical"
        return payload

    monkeypatch.setattr("app.core.report_evidence_service.ReportEvidenceService.collect", force_high_risk)

    response = client.post(f"/api/enhanced-reports/{case_id}/generate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["report_status"] == "waiting_review"
    assert payload["generation_metadata"]["guardrails"]["publication_status"] == "waiting_review"
    assert payload["generation_metadata"]["guardrails"]["review_required"] is True
    versions = client.get(f"/api/enhanced-reports/{case_id}/versions")
    assert versions.status_code == 200
    assert versions.json()["versions"][0]["status"] == "waiting_review"


def test_report_missing_critical_section_content_fails_guardrail(tmp_path: Path, monkeypatch) -> None:
    from app.core.enhanced_report_service import (
        EnhancedReportCitation,
        EnhancedReportPayload,
        EnhancedReportSection,
    )

    def fake_build_report(self, *, case_id: str, evidence: dict[str, object]):
        return (
            EnhancedReportPayload(
                case_summary=EnhancedReportSection(
                    title="案例摘要",
                    content="",
                    confidence=0.92,
                    evidence_refs=["case_result"],
                ),
                diagnosis_conclusion=EnhancedReportSection(
                    title="诊断结论",
                    content="结论",
                    confidence=0.9,
                    evidence_refs=["case_result"],
                ),
                risk_assessment=EnhancedReportSection(
                    title="风险评估",
                    content="风险",
                    confidence=0.89,
                    evidence_refs=["case_result"],
                ),
                evidence_summary=EnhancedReportSection(
                    title="证据摘要",
                    content="证据摘要",
                    confidence=0.88,
                    evidence_refs=["case_result"],
                ),
                maintenance_actions=EnhancedReportSection(
                    title="维护建议",
                    content="维护建议",
                    confidence=0.87,
                    evidence_refs=["case_result"],
                ),
                applicability_and_limits=EnhancedReportSection(
                    title="适用边界",
                    content="适用边界",
                    confidence=0.86,
                    evidence_refs=["model_metadata"],
                ),
                similar_cases=[],
                appendix_metrics=[],
                citations=[
                    EnhancedReportCitation(
                        evidence_ref="case_result",
                        title="Case result",
                        excerpt="摘要",
                        evidence_type="case_result",
                        score=1.0,
                    )
                ],
            ),
            "enhanced_llm",
            {"llm_used": True},
        )

    monkeypatch.setattr("app.core.enhanced_report_service.EnhancedReportService._build_report", fake_build_report)

    client = _create_client(tmp_path)
    case_id = _create_case(client, LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy")

    response = client.post(f"/api/enhanced-reports/{case_id}/generate")

    assert response.status_code == 422
    assert "guardrail failed" in response.json()["detail"]
