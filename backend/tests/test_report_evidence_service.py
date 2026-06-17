from __future__ import annotations

from pathlib import Path

from app.core.knowledge_ingestion import KnowledgeIngestionService
from app.core.report_evidence_service import ReportEvidenceService
from app.core.settings import Settings
from app.main import create_app
from fastapi.testclient import TestClient


LITTLEMODEL_ROOT = Path(r"C:\Users\luzian\Desktop\littlemodel")


def _create_settings(tmp_path: Path) -> Settings:
    return Settings(
        backend_root=tmp_path,
        littlemodel_root=LITTLEMODEL_ROOT,
        knowledge_ingestion_enabled=True,
        knowledge_rag_enabled=True,
        chat_rag_enabled=True,
        knowledge_case_ingestion_enabled=True,
        enhanced_reports_enabled=True,
    )


def _create_case(client: TestClient, task_type: str, path: Path) -> str:
    with path.open("rb") as handle:
        upload = client.post("/api/upload", files={"file": (path.name, handle)})
    file_id = upload.json()["file"]["file_id"]
    diagnose = client.post("/api/diagnose", json={"file_id": file_id, "task_type": task_type})
    return diagnose.json()["case_id"]


def test_report_evidence_service_aggregates_case_model_knowledge_and_similar_cases(tmp_path: Path) -> None:
    settings = _create_settings(tmp_path)
    client = TestClient(create_app(settings))
    first_case = _create_case(client, "fault_diagnosis", LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy")
    _create_case(client, "fault_diagnosis", LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy")
    KnowledgeIngestionService(settings).ingest_default_sources()

    evidence = ReportEvidenceService(settings).collect(first_case)

    assert evidence["case_context"]["case_id"] == first_case
    assert evidence["model_context"]["model_name"]
    assert isinstance(evidence["retrieved_knowledge"]["chunks"], list)
    assert len(evidence["retrieved_knowledge"]["chunks"]) >= 1
    assert isinstance(evidence["similar_cases"], list)
    assert len(evidence["evidence_items"]) >= 3
