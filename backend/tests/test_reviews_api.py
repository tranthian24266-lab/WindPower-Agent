from __future__ import annotations

from pathlib import Path
from time import sleep, time

from fastapi.testclient import TestClient

from app.core.deepseek_client import DeepSeekChatResult
from app.core.report_evidence_service import ReportEvidenceService
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
        "embedded_worker_enabled": True,
    }
    payload.update(overrides)
    settings = Settings(**payload)
    return TestClient(create_app(settings))


def _create_case(client: TestClient) -> str:
    sample = LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy"
    with sample.open("rb") as handle:
        upload = client.post("/api/upload", files={"file": (sample.name, handle)})
    file_id = upload.json()["file"]["file_id"]
    diagnose = client.post("/api/diagnose", json={"file_id": file_id, "task_type": "fault_diagnosis"})
    return diagnose.json()["case_id"]


def _wait_for_run(client: TestClient, run_id: str, *, timeout_seconds: float = 20.0) -> dict[str, object]:
    deadline = time() + timeout_seconds
    while time() < deadline:
        response = client.get(f"/api/agent-runs/{run_id}")
        assert response.status_code == 200
        run = response.json()["run"]
        if run["status"] in {"succeeded", "failed", "cancelled", "waiting_review"}:
            return run
        sleep(0.2)
    raise AssertionError(f"Timed out waiting for run {run_id}")


def _force_high_risk_collect(self: ReportEvidenceService, case_id: str) -> dict[str, object]:
    payload = _force_high_risk_collect.original(self, case_id)
    payload["case_context"]["risk_level"] = "critical"
    payload["case_context"]["result"]["risk_level"] = "critical"
    return payload


def test_review_approval_resumes_waiting_report_run(tmp_path: Path, monkeypatch) -> None:
    class FakeDeepSeekClient:
        def __init__(self, settings: Settings):
            self.settings = settings

        def create_chat_completion(self, **kwargs) -> DeepSeekChatResult:
            return DeepSeekChatResult(
                content="""
                {
                  "case_summary": {"title": "案例摘要", "content": "摘要", "confidence": 0.91, "evidence_refs": ["case_result"]},
                  "diagnosis_conclusion": {"title": "诊断结论", "content": "结论", "confidence": 0.9, "evidence_refs": ["case_result"]},
                  "risk_assessment": {"title": "风险评估", "content": "高风险。", "confidence": 0.88, "evidence_refs": ["model_metadata"]},
                  "evidence_summary": {"title": "证据摘要", "content": "证据摘要", "confidence": 0.87, "evidence_refs": ["model_metadata"]},
                  "maintenance_actions": {"title": "维护建议", "content": "建议停机复核。", "confidence": 0.86, "evidence_refs": ["model_metadata"]},
                  "applicability_and_limits": {"title": "适用边界", "content": "适用边界", "confidence": 0.85, "evidence_refs": ["model_metadata"]},
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
    _force_high_risk_collect.original = ReportEvidenceService.collect  # type: ignore[attr-defined]
    monkeypatch.setattr("app.core.report_evidence_service.ReportEvidenceService.collect", _force_high_risk_collect)

    with _create_client(tmp_path) as client:
        case_id = _create_case(client)
        response = client.post(
            "/api/agent-runs",
            json={"run_type": "enhanced_report", "case_id": case_id, "input": {"case_id": case_id}},
        )
        assert response.status_code == 202
        run_id = response.json()["run_id"]

        run = _wait_for_run(client, run_id)
        assert run["status"] == "waiting_review"
        assert run["output"]["review_task_id"]
        review_task_id = run["output"]["review_task_id"]

        listed = client.get("/api/reviews", params={"status": "pending"})
        assert listed.status_code == 200
        assert listed.json()["count"] == 1

        detail = client.get(f"/api/reviews/{review_task_id}")
        assert detail.status_code == 200
        assert detail.json()["task"]["actions"][0]["action"] == "created"

        approved = client.post(
            f"/api/reviews/{review_task_id}/approve",
            json={"reviewer": "qa", "comment": "evidence chain accepted"},
        )
        assert approved.status_code == 200
        assert approved.json()["task"]["status"] == "approved"

        approved_run = client.get(f"/api/agent-runs/{run_id}")
        assert approved_run.status_code == 200
        assert approved_run.json()["run"]["status"] == "succeeded"

        versions = client.get(f"/api/enhanced-reports/{case_id}/versions")
        assert versions.status_code == 200
        assert versions.json()["versions"][0]["status"] == "ready"


def test_review_reject_marks_run_failed_and_keeps_audit_trail(tmp_path: Path, monkeypatch) -> None:
    class FakeDeepSeekClient:
        def __init__(self, settings: Settings):
            self.settings = settings

        def create_chat_completion(self, **kwargs) -> DeepSeekChatResult:
            return DeepSeekChatResult(
                content="""
                {
                  "case_summary": {"title": "案例摘要", "content": "摘要", "confidence": 0.91, "evidence_refs": ["case_result"]},
                  "diagnosis_conclusion": {"title": "诊断结论", "content": "结论", "confidence": 0.9, "evidence_refs": ["case_result"]},
                  "risk_assessment": {"title": "风险评估", "content": "高风险。", "confidence": 0.88, "evidence_refs": ["model_metadata"]},
                  "evidence_summary": {"title": "证据摘要", "content": "证据摘要", "confidence": 0.87, "evidence_refs": ["model_metadata"]},
                  "maintenance_actions": {"title": "维护建议", "content": "建议停机复核。", "confidence": 0.86, "evidence_refs": ["model_metadata"]},
                  "applicability_and_limits": {"title": "适用边界", "content": "适用边界", "confidence": 0.85, "evidence_refs": ["model_metadata"]},
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
    _force_high_risk_collect.original = ReportEvidenceService.collect  # type: ignore[attr-defined]
    monkeypatch.setattr("app.core.report_evidence_service.ReportEvidenceService.collect", _force_high_risk_collect)

    with _create_client(tmp_path) as client:
        case_id = _create_case(client)
        response = client.post(f"/api/enhanced-reports/{case_id}/generate")
        assert response.status_code == 200
        payload = response.json()
        assert payload["report_status"] == "waiting_review"
        assert payload["review_task_id"]

        rejected = client.post(
            f"/api/reviews/{payload['review_task_id']}/reject",
            json={"reviewer": "qa", "comment": "evidence still too weak"},
        )
        assert rejected.status_code == 200
        task = rejected.json()["task"]
        assert task["status"] == "rejected"
        assert task["actions"][-1]["action"] == "rejected"

        run = client.get(f"/api/agent-runs/{payload['run_id']}")
        assert run.status_code == 200
        assert run.json()["run"]["status"] == "failed"

        versions = client.get(f"/api/enhanced-reports/{case_id}/versions")
        assert versions.status_code == 200
        assert versions.json()["versions"][0]["status"] == "rejected"


def test_review_request_changes_marks_report_for_rework(tmp_path: Path, monkeypatch) -> None:
    class FakeDeepSeekClient:
        def __init__(self, settings: Settings):
            self.settings = settings

        def create_chat_completion(self, **kwargs) -> DeepSeekChatResult:
            return DeepSeekChatResult(
                content="""
                {
                  "case_summary": {"title": "案例摘要", "content": "摘要", "confidence": 0.91, "evidence_refs": ["case_result"]},
                  "diagnosis_conclusion": {"title": "诊断结论", "content": "结论", "confidence": 0.9, "evidence_refs": ["case_result"]},
                  "risk_assessment": {"title": "风险评估", "content": "高风险。", "confidence": 0.88, "evidence_refs": ["model_metadata"]},
                  "evidence_summary": {"title": "证据摘要", "content": "证据摘要", "confidence": 0.87, "evidence_refs": ["model_metadata"]},
                  "maintenance_actions": {"title": "维护建议", "content": "建议停机复核。", "confidence": 0.86, "evidence_refs": ["model_metadata"]},
                  "applicability_and_limits": {"title": "适用边界", "content": "适用边界", "confidence": 0.85, "evidence_refs": ["model_metadata"]},
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
    _force_high_risk_collect.original = ReportEvidenceService.collect  # type: ignore[attr-defined]
    monkeypatch.setattr("app.core.report_evidence_service.ReportEvidenceService.collect", _force_high_risk_collect)

    with _create_client(tmp_path) as client:
        case_id = _create_case(client)
        response = client.post(f"/api/enhanced-reports/{case_id}/generate")
        assert response.status_code == 200
        payload = response.json()

        changed = client.post(
            f"/api/reviews/{payload['review_task_id']}/request-changes",
            json={"reviewer": "qa", "comment": "please add stronger supporting evidence"},
        )
        assert changed.status_code == 200
        task = changed.json()["task"]
        assert task["status"] == "changes_requested"
        assert task["actions"][-1]["action"] == "changes_requested"

        run = client.get(f"/api/agent-runs/{payload['run_id']}")
        assert run.status_code == 200
        assert run.json()["run"]["status"] == "failed"

        versions = client.get(f"/api/enhanced-reports/{case_id}/versions")
        assert versions.status_code == 200
        assert versions.json()["versions"][0]["status"] == "changes_requested"
