from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.knowledge_ingestion import KnowledgeIngestionService
from app.core.settings import Settings
from app.main import create_app


LITTLEMODEL_ROOT = Path(r"C:\Users\luzian\Desktop\littlemodel")


def _create_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        backend_root=tmp_path,
        littlemodel_root=LITTLEMODEL_ROOT,
        agent_mode="local",
        deepseek_api_key=None,
        knowledge_ingestion_enabled=True,
        knowledge_rag_enabled=True,
        chat_rag_enabled=True,
        knowledge_case_ingestion_enabled=True,
        enhanced_reports_enabled=True,
    )
    KnowledgeIngestionService(settings).ingest_default_sources()
    return TestClient(create_app(settings))


def _create_case(client: TestClient, task_type: str, path: Path) -> str:
    with path.open("rb") as handle:
        upload = client.post("/api/upload", files={"file": (path.name, handle)})
    file_id = upload.json()["file"]["file_id"]
    diagnose = client.post("/api/diagnose", json={"file_id": file_id, "task_type": task_type})
    return diagnose.json()["case_id"]


def test_chat_run_is_persisted_and_queryable(tmp_path: Path) -> None:
    client = _create_client(tmp_path)
    case_id = _create_case(
        client,
        "fault_diagnosis",
        LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy",
    )

    response = client.post("/api/chat", json={"case_id": case_id, "question": "请总结当前案例。"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"]

    detail = client.get(f"/api/agent-runs/{payload['run_id']}")
    assert detail.status_code == 200
    run = detail.json()["run"]
    assert run["run_type"] == "chat_answer"
    assert run["status"] == "succeeded"
    assert run["case_id"] == case_id
    assert run["step_count"] >= 1
    assert run["tool_call_count"] >= 1
    assert run["steps"][0]["tool_calls"][0]["tool_name"] == "chat.answer"

    listing = client.get("/api/agent-runs", params={"case_id": case_id, "run_type": "chat_answer"})
    assert listing.status_code == 200
    assert any(item["run_id"] == payload["run_id"] for item in listing.json()["runs"])


def test_enhanced_report_run_is_linked_to_report_version(tmp_path: Path) -> None:
    client = _create_client(tmp_path)
    case_id = _create_case(
        client,
        "fault_diagnosis",
        LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy",
    )

    response = client.post(f"/api/enhanced-reports/{case_id}/generate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"]

    detail = client.get(f"/api/agent-runs/{payload['run_id']}")
    assert detail.status_code == 200
    run = detail.json()["run"]
    assert run["run_type"] == "enhanced_report"
    assert run["status"] == "succeeded"
    assert run["steps"][0]["tool_calls"][0]["tool_name"] == "enhanced_report.generate"

    report = client.get(f"/api/enhanced-reports/{case_id}", params={"report_version_id": payload["report_version_id"]})
    assert report.status_code == 200
    assert report.json()["run_id"] == payload["run_id"]
