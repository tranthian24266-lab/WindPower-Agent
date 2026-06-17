from __future__ import annotations

import json
from pathlib import Path

from app.core.case_store import CaseStoreService
from app.core.knowledge_ingestion import KnowledgeIngestionService
from app.core.knowledge_repository import KnowledgeRepository
from app.core.settings import Settings
from app.core.vector_index_service import VectorIndexService


def _create_settings(tmp_path: Path) -> Settings:
    backend_root = tmp_path / "backend"
    backend_root.mkdir(parents=True, exist_ok=True)
    knowledge_root = tmp_path / "knowledge_base"
    littlemodel_root = tmp_path / "littlemodel"
    (littlemodel_root / "fault_diagnosis" / "docs").mkdir(parents=True, exist_ok=True)
    (knowledge_root / "domain_knowledge").mkdir(parents=True, exist_ok=True)
    (knowledge_root / "models").mkdir(parents=True, exist_ok=True)
    (knowledge_root / "raw" / "papers").mkdir(parents=True, exist_ok=True)
    (knowledge_root / "domain_knowledge" / "fault_diagnosis.md").write_text(
        "# Fault Diagnosis\n\n"
        "Confidence near 0.5 should be reviewed with more samples.\n\n"
        "High risk cases need follow-up inspection before maintenance decisions.\n",
        encoding="utf-8",
    )
    (knowledge_root / "models" / "fault_diagnosis.md").write_text(
        "# fault_diagnosis\n\n"
        "Default model focuses on healthy versus damaged discrimination.\n\n"
        "It should not be treated as a root-cause locator by itself.\n",
        encoding="utf-8",
    )
    (knowledge_root / "raw" / "papers" / "fault_diagnosis_paper_summary.md").write_text(
        "# Fault Diagnosis Paper Summary\n\nThe local reproduction uses the public NREL/OEDI dataset only.\n",
        encoding="utf-8",
    )
    (littlemodel_root / "fault_diagnosis" / "README.md").write_text(
        "# fault_diagnosis\n\nBinary healthy versus damaged classifier.\n",
        encoding="utf-8",
    )
    (littlemodel_root / "fault_diagnosis" / "model_card.json").write_text(
        '{"model_id":"fault-demo","paper_title":"Fault Demo Paper","dataset":"NREL/OEDI"}',
        encoding="utf-8",
    )
    (littlemodel_root / "fault_diagnosis" / "docs" / "reproduce_summary.md").write_text(
        "# Reproduce Summary\n\nThe public-dataset branch was reproduced locally.\n",
        encoding="utf-8",
    )
    return Settings(
        backend_root=backend_root,
        littlemodel_root=littlemodel_root,
        knowledge_ingestion_enabled=True,
        knowledge_rag_enabled=True,
    )


def test_knowledge_migration_and_ingestion(tmp_path: Path) -> None:
    settings = _create_settings(tmp_path)
    repository = KnowledgeRepository(settings.database_path)

    with repository.database.connect() as connection:
        table_names = {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }

    assert {
        "knowledge_documents",
        "knowledge_chunks",
        "knowledge_ingestion_runs",
        "retrieval_events",
    }.issubset(table_names)

    service = KnowledgeIngestionService(settings, repository)
    result = service.ingest_default_sources()

    assert result["status"] == "completed"
    assert result["discovered_count"] == 6
    assert result["processed_count"] == 6
    assert result["failed_count"] == 0

    documents = repository.list_documents()
    assert len(documents) == 6
    assert any(document["source_type"] == "littlemodel_model_card" for document in documents)
    assert any(document["source_type"] == "curated_papers" for document in documents)

    chunks = repository.list_chunks(task_type="fault_diagnosis")
    assert len(chunks) >= 2
    assert all(chunk["task_type"] == "fault_diagnosis" for chunk in chunks)

    manifest_files = list(settings.knowledge_index_manifest_path.glob("*.json"))
    processed_files = list(settings.knowledge_processed_path.glob("*.json"))
    assert len(manifest_files) == 6
    assert len(processed_files) == 6


def test_knowledge_ingestion_can_include_historical_cases_when_flag_enabled(tmp_path: Path) -> None:
    settings = _create_settings(tmp_path)
    settings = Settings(
        backend_root=settings.backend_root,
        littlemodel_root=settings.littlemodel_root,
        knowledge_ingestion_enabled=True,
        knowledge_rag_enabled=True,
        knowledge_case_ingestion_enabled=True,
    )
    store = CaseStoreService(settings.database_path)
    output_dir = settings.outputs_path / "case-demo"
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "result.json"
    result_path.write_text(
        json.dumps(
            {
                "task_type": "fault_diagnosis",
                "prediction": "damaged",
                "confidence": 0.91,
                "risk_level": "warning",
                "summary": "Detected damaged pattern in the gearbox signal.",
                "recommendation": "Inspect the gearbox and verify the source channel.",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    upload_path = settings.uploads_path / "sample.npy"
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_bytes(b"demo")
    store.save_uploaded_file(
        {
            "file_id": "file-demo",
            "original_filename": "sample.npy",
            "stored_path": str(upload_path),
            "suffix": ".npy",
            "content_type": "application/octet-stream",
            "size_bytes": 4,
            "created_at": "2026-06-04T00:00:00+00:00",
        }
    )
    store.save_diagnosis_case(
        {
            "case_id": "case-demo",
            "file_id": "file-demo",
            "task_type": "fault_diagnosis",
            "model_id": "fault-demo",
            "model_name": "Fault Demo",
            "status": "success",
            "risk_level": "warning",
            "result_json_path": str(result_path),
            "output_dir": str(output_dir),
            "created_at": "2026-06-04T00:00:00+00:00",
            "report_html_path": None,
            "report_pdf_path": None,
        }
    )

    repository = KnowledgeRepository(settings.database_path)
    result = KnowledgeIngestionService(settings, repository).ingest_default_sources()

    assert result["status"] == "completed"
    assert result["discovered_count"] == 7

    case_documents = [doc for doc in repository.list_documents() if doc["source_type"] == "historical_case_summary"]
    assert len(case_documents) == 1
    assert case_documents[0]["metadata"]["case_id"] == "case-demo"

    case_chunks = repository.list_chunks(source_type="historical_case_summary")
    assert len(case_chunks) >= 1
    assert "Historical Case case-demo" in case_chunks[0]["content"]


class _FakeQdrantClient:
    def __init__(self) -> None:
        self.collections: dict[str, dict[str, object]] = {}
        self.points: dict[str, dict[str, object]] = {}

    def collection_exists(self, name: str) -> bool:
        return name in self.collections

    def create_collection(self, collection_name: str, vectors_config: object) -> None:
        self.collections[collection_name] = {"vectors_config": vectors_config}

    def delete(self, collection_name: str, points_selector: object, wait: bool = True) -> None:
        document_id = None
        if isinstance(points_selector, dict):
            matches = points_selector.get("filter", {}).get("must", [])
            if matches:
                document_id = matches[0].get("match", {}).get("value")
        if document_id is None:
            return
        for point_id in list(self.points):
            payload = self.points[point_id].get("payload", {})
            if payload.get("document_id") == document_id:
                self.points.pop(point_id, None)

    def upsert(self, collection_name: str, points: list[object], wait: bool = True) -> None:
        for point in points:
            if isinstance(point, dict):
                point_id = point["id"]
                payload = point["payload"]
                vector = point["vector"]
            else:
                point_id = point.id
                payload = point.payload
                vector = point.vector
            self.points[str(point_id)] = {"payload": payload, "vector": vector}

    def get_collection(self, collection_name: str) -> dict[str, object]:
        return {
            "name": collection_name,
            "points_count": len(self.points),
        }


def test_knowledge_ingestion_can_sync_qdrant_metadata_when_enabled(tmp_path: Path, monkeypatch) -> None:
    base_settings = _create_settings(tmp_path)
    settings = Settings(
        backend_root=base_settings.backend_root,
        littlemodel_root=base_settings.littlemodel_root,
        knowledge_ingestion_enabled=True,
        knowledge_rag_enabled=True,
        qdrant_enabled=True,
        qdrant_url="http://127.0.0.1:6333",
    )
    repository = KnowledgeRepository(settings.database_path)
    fake_client = _FakeQdrantClient()
    monkeypatch.setattr(VectorIndexService, "_create_client", lambda self: fake_client)

    result = KnowledgeIngestionService(settings, repository).ingest_default_sources()

    assert result["status"] == "completed"
    assert fake_client.collections[settings.qdrant_collection_name]
    chunks = repository.list_chunks(task_type="fault_diagnosis")
    assert chunks
    assert all(chunk["embedding_model"] == settings.embedding_model_name for chunk in chunks)
    assert any(chunk["vector_store_id"] for chunk in chunks)
