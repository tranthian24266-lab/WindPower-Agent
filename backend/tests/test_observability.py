from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.knowledge_ingestion import KnowledgeIngestionService
from app.core.retrieval_service import RetrievalService
from app.core.settings import Settings
from app.main import create_app


LITTLEMODEL_ROOT = Path(r"C:\Users\luzian\Desktop\littlemodel")


def _read_events(settings: Settings) -> list[dict[str, object]]:
    path = settings.telemetry_path / "events.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _create_settings(tmp_path: Path, **overrides: object) -> Settings:
    payload: dict[str, object] = {
        "backend_root": tmp_path,
        "littlemodel_root": LITTLEMODEL_ROOT,
        "knowledge_ingestion_enabled": True,
        "knowledge_rag_enabled": True,
        "chat_rag_enabled": True,
        "knowledge_case_ingestion_enabled": True,
        "enhanced_reports_enabled": True,
        "observability_enabled": True,
    }
    payload.update(overrides)
    return Settings(**payload)


def _create_client(tmp_path: Path, **overrides: object) -> tuple[TestClient, Settings]:
    settings = _create_settings(tmp_path, **overrides)
    KnowledgeIngestionService(settings).ingest_default_sources()
    return TestClient(create_app(settings)), settings


def _create_case(client: TestClient, task_type: str, path: Path) -> str:
    with path.open("rb") as handle:
        upload = client.post("/api/upload", files={"file": (path.name, handle)})
    file_id = upload.json()["file"]["file_id"]
    diagnose = client.post("/api/diagnose", json={"file_id": file_id, "task_type": task_type})
    return diagnose.json()["case_id"]


def test_retrieval_summary_is_logged(tmp_path: Path) -> None:
    settings = _create_settings(tmp_path)
    KnowledgeIngestionService(settings).ingest_default_sources()
    service = RetrievalService(settings)

    response = service.search("confidence damaged samples", task_type="fault_diagnosis", top_k=2)

    assert response.retrieval_event_id
    events = _read_events(settings)
    retrieval_events = [item for item in events if item["event_type"] == "retrieval_summary"]
    assert retrieval_events
    payload = retrieval_events[-1]["payload"]
    assert payload["retrieval_mode"] in {"local_dense", "qdrant_dense", "no_results"}
    assert payload["actual_hits"] >= 0
    assert payload["top_k"] == 2


def test_chat_logs_deepseek_and_chat_summary(tmp_path: Path, monkeypatch) -> None:
    class FakeResponse:
        text = ""

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": "这是 DeepSeek 回答。",
                            "reasoning_content": "先分析再回答。",
                        }
                    }
                ],
                "usage": {"total_tokens": 42},
            }

    monkeypatch.setattr("app.core.deepseek_client.httpx.post", lambda *args, **kwargs: FakeResponse())

    client, settings = _create_client(
        tmp_path,
        agent_mode="auto",
        deepseek_api_key="test-key",
    )
    case_id = _create_case(client, "fault_diagnosis", LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy")

    response = client.post("/api/chat", json={"case_id": case_id, "question": "请解释这次结果"})

    assert response.status_code == 200
    events = _read_events(settings)
    deepseek_events = [item for item in events if item["event_type"] == "deepseek_call"]
    chat_events = [item for item in events if item["event_type"] == "chat_answer_summary"]
    assert deepseek_events
    assert chat_events
    assert deepseek_events[-1]["payload"]["success"] is True
    assert deepseek_events[-1]["payload"]["usage"]["total_tokens"] == 42
    assert chat_events[-1]["payload"]["mode"] == "rag_deepseek_api"


def test_enhanced_report_generation_is_logged(tmp_path: Path) -> None:
    client, settings = _create_client(tmp_path)
    case_id = _create_case(client, "fault_diagnosis", LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy")
    _create_case(client, "fault_diagnosis", LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy")

    response = client.post(f"/api/enhanced-reports/{case_id}/generate")

    assert response.status_code == 200
    events = _read_events(settings)
    report_events = [item for item in events if item["event_type"] == "enhanced_report_generation"]
    assert report_events
    payload = report_events[-1]["payload"]
    assert payload["case_id"] == case_id
    assert payload["source_mode"] in {"enhanced_rule_fallback", "enhanced_llm"}
    assert payload["chunk_count"] >= 0
    assert payload["citation_count"] >= 1
