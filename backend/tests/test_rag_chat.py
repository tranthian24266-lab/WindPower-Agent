from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.knowledge_ingestion import KnowledgeIngestionService
from app.core.settings import Settings
from app.main import create_app


LITTLEMODEL_ROOT = Path(r"C:\Users\luzian\Desktop\littlemodel")


def _create_settings(tmp_path: Path) -> Settings:
    backend_root = tmp_path / "backend"
    backend_root.mkdir(parents=True, exist_ok=True)
    knowledge_root = tmp_path / "knowledge_base"
    (knowledge_root / "domain_knowledge").mkdir(parents=True, exist_ok=True)
    (knowledge_root / "models").mkdir(parents=True, exist_ok=True)
    (knowledge_root / "domain_knowledge" / "fault_diagnosis.md").write_text(
        "# Fault Diagnosis\n\n"
        "Confidence near 0.5 should be reviewed with more samples.\n\n"
        "High risk cases need follow-up inspection before maintenance decisions.\n",
        encoding="utf-8",
    )
    (knowledge_root / "models" / "fault_diagnosis.md").write_text(
        "# Model Notes\n\n"
        "The model separates healthy and damaged conditions.\n\n"
        "It should not be used as a stand-alone root-cause locator.\n",
        encoding="utf-8",
    )
    return Settings(
        backend_root=backend_root,
        littlemodel_root=LITTLEMODEL_ROOT,
        agent_mode="local",
        deepseek_api_key=None,
        knowledge_ingestion_enabled=True,
        knowledge_rag_enabled=True,
        chat_rag_enabled=True,
    )


def _create_case(client: TestClient, path: Path) -> str:
    with path.open("rb") as handle:
        upload = client.post("/api/upload", files={"file": (path.name, handle)})
    file_id = upload.json()["file"]["file_id"]
    diagnose = client.post("/api/diagnose", json={"file_id": file_id, "task_type": "fault_diagnosis"})
    return diagnose.json()["case_id"]


def test_chat_returns_citations_when_rag_flag_enabled(tmp_path: Path) -> None:
    settings = _create_settings(tmp_path)
    KnowledgeIngestionService(settings).ingest_default_sources()
    client = TestClient(create_app(settings))
    case_id = _create_case(client, LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy")

    response = client.post("/api/chat", json={"case_id": case_id, "question": "Explain the risk and confidence"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "rag_rule_based_local"
    assert payload["knowledge_mode"] == "local_dense"
    assert payload["retrieval_event_id"]
    assert len(payload["citations"]) >= 1
    assert "prediction" in payload["answer"]


def test_chat_history_persists_citations_and_retrieval_metadata(tmp_path: Path) -> None:
    settings = _create_settings(tmp_path)
    KnowledgeIngestionService(settings).ingest_default_sources()
    client = TestClient(create_app(settings))
    case_id = _create_case(client, LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy")

    response = client.post("/api/chat", json={"case_id": case_id, "question": "Explain the risk and confidence"})
    payload = response.json()

    history = client.get(f"/api/chat/history/{case_id}")
    assert history.status_code == 200
    assistant_messages = [item for item in history.json()["messages"] if item["role"] == "assistant"]
    assert assistant_messages
    latest = assistant_messages[-1]
    assert latest["citations"]
    assert latest["knowledge_mode"] == payload["knowledge_mode"]
    assert latest["retrieval_event_id"] == payload["retrieval_event_id"]
