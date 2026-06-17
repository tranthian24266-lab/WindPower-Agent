from __future__ import annotations

from pathlib import Path
from time import sleep, time

from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.main import create_app


LITTLEMODEL_ROOT = Path(r"C:\Users\luzian\Desktop\littlemodel")


def _create_client(tmp_path: Path, **overrides: object) -> TestClient:
    payload: dict[str, object] = {
        "backend_root": tmp_path,
        "littlemodel_root": LITTLEMODEL_ROOT,
        "agent_mode": "local",
        "deepseek_api_key": None,
        "knowledge_ingestion_enabled": True,
        "knowledge_rag_enabled": True,
        "chat_rag_enabled": True,
        "knowledge_case_ingestion_enabled": True,
        "enhanced_reports_enabled": True,
        "embedded_worker_enabled": True,
        "audit_enabled": True,
    }
    payload.update(overrides)
    return TestClient(create_app(Settings(**payload)))


def _create_case(client: TestClient) -> str:
    sample = LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy"
    with sample.open("rb") as handle:
        upload = client.post("/api/upload", files={"file": (sample.name, handle)})
    file_id = upload.json()["file"]["file_id"]
    diagnose = client.post("/api/diagnose", json={"file_id": file_id, "task_type": "fault_diagnosis"})
    return diagnose.json()["case_id"]


def _wait_for_run(client: TestClient, run_id: str, timeout_seconds: float = 20.0) -> dict[str, object]:
    deadline = time() + timeout_seconds
    while time() < deadline:
        response = client.get(f"/api/agent-runs/{run_id}")
        run = response.json()["run"]
        if run["status"] in {"succeeded", "failed", "cancelled", "waiting_review"}:
            return run
        sleep(0.2)
    raise AssertionError(f"Timed out waiting for run {run_id}")


def test_async_chat_run_records_agent_handoffs_and_audit_logs(tmp_path: Path) -> None:
    with _create_client(tmp_path, rbac_enabled=True) as client:
        case_id = _create_case(client)
        response = client.post(
            "/api/agent-runs",
            headers={"X-Actor-Role": "operator", "X-Actor-Id": "ops-b"},
            json={
                "run_type": "chat_answer",
                "case_id": case_id,
                "input": {
                    "case_id": case_id,
                    "question": "请总结当前案例状态。",
                },
            },
        )
        assert response.status_code == 202
        run_id = response.json()["run_id"]

        run = _wait_for_run(client, run_id)
        assert run["status"] == "succeeded"

        timeline = client.get(f"/api/agent-runs/{run_id}/timeline")
        assert timeline.status_code == 200
        telemetry_names = [item["name"] for item in timeline.json()["timeline"] if item["kind"] == "telemetry"]
        assert "agent_handoff" in telemetry_names
        assert "agent_orchestration_summary" in telemetry_names

        audit_summary = client.get("/api/system/audit-summary")
        assert audit_summary.status_code == 200
        counts = audit_summary.json()["counts_by_action"]
        assert counts["agent_run.create"] >= 1

        audit_logs = client.get("/api/system/audit-logs", params={"limit": 20})
        assert audit_logs.status_code == 200
        actions = [item["action"] for item in audit_logs.json()["logs"]]
        assert "agent_run.create" in actions

        specialist_summary = client.get("/api/system/specialist-summary")
        assert specialist_summary.status_code == 200
        specialist_payload = specialist_summary.json()
        assert specialist_payload["counts_by_specialist"]["diagnosis_agent"] >= 1
        assert specialist_payload["counts_by_specialist"]["retrieval_agent"] >= 1
        assert specialist_payload["counts_by_workflow"]["chat_answer"] >= 1

        config_summary = client.get("/api/system/config-summary")
        assert config_summary.status_code == 200
        integrations = config_summary.json()["integrations"]
        assert integrations["database_backend"] == "sqlite"
        assert integrations["rbac_enabled"] is True
        assert integrations["audit_enabled"] is True
