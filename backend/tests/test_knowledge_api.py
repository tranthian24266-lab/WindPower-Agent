from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.core.vector_index_service import VectorIndexService
from app.main import create_app


def _create_settings(tmp_path: Path) -> Settings:
    backend_root = tmp_path / "backend"
    backend_root.mkdir(parents=True, exist_ok=True)
    knowledge_root = tmp_path / "knowledge_base"
    littlemodel_root = tmp_path / "littlemodel"
    (knowledge_root / "domain_knowledge").mkdir(parents=True, exist_ok=True)
    (knowledge_root / "models").mkdir(parents=True, exist_ok=True)
    (knowledge_root / "raw" / "datasets").mkdir(parents=True, exist_ok=True)
    (littlemodel_root / "anomaly_detection" / "docs").mkdir(parents=True, exist_ok=True)
    (knowledge_root / "domain_knowledge" / "anomaly_detection.md").write_text(
        "# Anomaly Detection\n\nReconstruction error is the main anomaly signal.\n",
        encoding="utf-8",
    )
    (knowledge_root / "models" / "anomaly_detection.md").write_text(
        "# Model Notes\n\nTransfer-learning quality depends on source-target similarity.\n",
        encoding="utf-8",
    )
    (knowledge_root / "raw" / "datasets" / "anomaly_detection_dataset_summary.md").write_text(
        "# Dataset Summary\n\nCARE To Compare Wind Farm A is the actual local dataset.\n",
        encoding="utf-8",
    )
    (littlemodel_root / "anomaly_detection" / "README.md").write_text(
        "# anomaly_detection\n\nAutoencoder transfer-learning detector.\n",
        encoding="utf-8",
    )
    (littlemodel_root / "anomaly_detection" / "model_card.json").write_text(
        '{"model_id":"ad-demo","paper_title":"AD Demo Paper","dataset":"CARE To Compare"}',
        encoding="utf-8",
    )
    (littlemodel_root / "anomaly_detection" / "docs" / "original_README.md").write_text(
        "# Original README\n\nSource turbine 13 and target turbine 10.\n",
        encoding="utf-8",
    )
    return Settings(
        backend_root=backend_root,
        littlemodel_root=littlemodel_root,
        knowledge_ingestion_enabled=True,
        knowledge_rag_enabled=True,
    )


def test_knowledge_api_ingest_and_list(tmp_path: Path) -> None:
    client = TestClient(create_app(_create_settings(tmp_path)))

    ingest = client.post("/api/knowledge/ingest", json={"source_scope": "api_test"})
    assert ingest.status_code == 200
    assert ingest.json()["processed_count"] == 6

    documents = client.get("/api/knowledge/documents")
    assert documents.status_code == 200
    assert documents.json()["count"] == 6

    first_document_id = documents.json()["documents"][0]["document_id"]
    chunks = client.get("/api/knowledge/chunks", params={"document_id": first_document_id, "limit": 10})
    assert chunks.status_code == 200
    assert chunks.json()["count"] >= 1

    runs = client.get("/api/knowledge/ingestion-runs")
    assert runs.status_code == 200
    assert runs.json()["count"] == 1
    assert runs.json()["runs"][0]["source_scope"] == "api_test"


class _FakeKnowledgeApiQdrantClient:
    def __init__(self) -> None:
        self.collections: dict[str, dict[str, object]] = {}
        self.points: dict[str, dict[str, object]] = {}
        self.payload_indexes: list[str] = []

    def collection_exists(self, name: str) -> bool:
        return name in self.collections

    def create_collection(self, collection_name: str, vectors_config: object) -> None:
        self.collections[collection_name] = {"vectors_config": vectors_config}

    def delete(self, collection_name: str, points_selector: object, wait: bool = True) -> None:
        self.points.clear()

    def upsert(self, collection_name: str, points: list[object], wait: bool = True) -> None:
        for point in points:
            if isinstance(point, dict):
                self.points[str(point["id"])] = point
            else:
                self.points[str(point.id)] = {"id": point.id, "payload": point.payload, "vector": point.vector}

    def get_collection(self, collection_name: str) -> dict[str, object]:
        return {
            "name": collection_name,
            "points_count": len(self.points),
            "payload_schema": {field_name: {"data_type": "keyword"} for field_name in self.payload_indexes},
        }

    def create_payload_index(self, collection_name: str, field_name: str, field_schema: object) -> None:
        if field_name not in self.payload_indexes:
            self.payload_indexes.append(field_name)


def test_knowledge_api_reindex_and_status(tmp_path: Path, monkeypatch) -> None:
    base_settings = _create_settings(tmp_path)
    settings = Settings(
        backend_root=base_settings.backend_root,
        littlemodel_root=base_settings.littlemodel_root,
        knowledge_ingestion_enabled=True,
        knowledge_rag_enabled=True,
        qdrant_enabled=True,
        qdrant_url="http://127.0.0.1:6333",
    )
    fake_client = _FakeKnowledgeApiQdrantClient()
    monkeypatch.setattr(VectorIndexService, "_create_client", lambda self: fake_client)
    client = TestClient(create_app(settings))

    ingest = client.post("/api/knowledge/ingest", json={"source_scope": "api_test"})
    assert ingest.status_code == 200

    status = client.get("/api/knowledge/index-status")
    assert status.status_code == 200
    assert status.json()["qdrant_enabled"] is True
    assert status.json()["embedding_provider_resolved"] == "local_ngram"
    assert status.json()["remote_ping_ok"] is True

    reindex = client.post("/api/knowledge/reindex", json={"force_recreate": False})
    assert reindex.status_code == 200
    assert reindex.json()["status"] == "ok"
    assert reindex.json()["indexed_count"] >= 1

    refreshed_status = client.get("/api/knowledge/index-status")
    assert refreshed_status.status_code == 200
    assert "metadata.task_type" in refreshed_status.json()["payload_indexes"]
    assert refreshed_status.json()["last_reindex_status"] == "ok"
    assert refreshed_status.json()["last_reindex_at"] is not None


def test_knowledge_api_reindex_accepts_empty_body(tmp_path: Path, monkeypatch) -> None:
    base_settings = _create_settings(tmp_path)
    settings = Settings(
        backend_root=base_settings.backend_root,
        littlemodel_root=base_settings.littlemodel_root,
        knowledge_ingestion_enabled=True,
        knowledge_rag_enabled=True,
        qdrant_enabled=True,
        qdrant_url="http://127.0.0.1:6333",
    )
    fake_client = _FakeKnowledgeApiQdrantClient()
    monkeypatch.setattr(VectorIndexService, "_create_client", lambda self: fake_client)
    client = TestClient(create_app(settings))

    ingest = client.post("/api/knowledge/ingest", json={"source_scope": "api_test"})
    assert ingest.status_code == 200

    reindex = client.post("/api/knowledge/reindex")
    assert reindex.status_code == 200
    assert reindex.json()["status"] == "ok"
