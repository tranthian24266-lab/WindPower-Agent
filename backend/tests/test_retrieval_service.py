from __future__ import annotations

from pathlib import Path

from app.core.knowledge_ingestion import KnowledgeIngestionService
from app.core.knowledge_repository import KnowledgeRepository
from app.core.retrieval_service import RetrievalService
from app.core.settings import Settings
from app.core.vector_index_service import VectorIndexService


def _create_settings(tmp_path: Path) -> Settings:
    backend_root = tmp_path / "backend"
    backend_root.mkdir(parents=True, exist_ok=True)
    knowledge_root = tmp_path / "knowledge_base"
    littlemodel_root = tmp_path / "littlemodel"
    littlemodel_root.mkdir(parents=True, exist_ok=True)
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
        littlemodel_root=littlemodel_root,
        knowledge_ingestion_enabled=True,
        knowledge_rag_enabled=True,
        qdrant_enabled=True,
        qdrant_url="http://127.0.0.1:6333",
    )


def test_retrieval_service_returns_ranked_chunks_and_logs_event(tmp_path: Path) -> None:
    settings = _create_settings(tmp_path)
    repository = KnowledgeRepository(settings.database_path)
    KnowledgeIngestionService(settings, repository).ingest_default_sources()

    service = RetrievalService(settings, repository=repository)
    response = service.search(
        "confidence damaged samples",
        task_type="fault_diagnosis",
        top_k=2,
    )

    assert response.mode == "local_dense"
    assert response.retrieval_event_id
    assert len(response.results) == 2
    assert response.results[0].task_type == "fault_diagnosis"
    assert response.results[0].score >= response.results[1].score

    with repository.database.connect() as connection:
        row = connection.execute(
            "SELECT query_text, top_k FROM retrieval_events WHERE retrieval_event_id = ?",
            (response.retrieval_event_id,),
        ).fetchone()

    assert row is not None
    assert row["query_text"] == "confidence damaged samples"
    assert row["top_k"] == 2


class _FakeSearchClient:
    def __init__(self) -> None:
        self.collections = {"knowledge_chunks": True}

    def collection_exists(self, name: str) -> bool:
        return name in self.collections

    def get_collection(self, collection_name: str) -> dict[str, object]:
        return {"name": collection_name}

    def search(
        self,
        *,
        collection_name: str,
        query_vector: list[float],
        limit: int,
        query_filter: object,
        with_payload: bool,
    ) -> list[object]:
        payload = {
            "chunk_id": "chunk-qdrant-1",
            "document_id": "doc-qdrant",
            "chunk_index": 0,
            "content": "Remote chunk for damaged confidence handling.",
            "summary": "Remote summary",
            "title": "Remote Title",
            "source_path": "knowledge_base/raw/remote.md",
            "source_type": "curated_remote",
            "task_type": "fault_diagnosis",
            "component": "curated_knowledge",
            "metadata": {"task_type": "fault_diagnosis"},
        }
        return [type("Hit", (), {"id": "chunk-qdrant-1", "score": 0.93, "payload": payload})()]


def test_retrieval_service_can_prefer_qdrant_when_enabled(tmp_path: Path, monkeypatch) -> None:
    settings = _create_settings(tmp_path)
    settings = Settings(
        backend_root=settings.backend_root,
        littlemodel_root=settings.littlemodel_root,
        knowledge_ingestion_enabled=True,
        knowledge_rag_enabled=True,
        qdrant_enabled=True,
        qdrant_prefer_remote=True,
        qdrant_url="http://127.0.0.1:6333",
    )
    repository = KnowledgeRepository(settings.database_path)
    KnowledgeIngestionService(settings, repository).ingest_default_sources()
    monkeypatch.setattr(VectorIndexService, "_create_client", lambda self: _FakeSearchClient())

    service = RetrievalService(settings, repository=repository)
    response = service.search("confidence damaged samples", task_type="fault_diagnosis", top_k=1)

    assert response.mode == "qdrant_dense"
    assert response.results[0].chunk_id == "chunk-qdrant-1"
    assert response.retrieval_event_id
