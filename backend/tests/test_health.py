from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.main import create_app


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "littlemodel_available" in payload


def test_config_summary_endpoint_returns_paths_and_runtime_flags(tmp_path: Path) -> None:
    backend_root = tmp_path / "backend"
    backend_root.mkdir()
    littlemodel_root = tmp_path / "littlemodel"
    littlemodel_root.mkdir()
    settings = Settings(
        backend_root=backend_root,
        littlemodel_root=littlemodel_root,
        deepseek_api_key="test-key",
        qdrant_enabled=True,
        qdrant_url="http://127.0.0.1:6333",
        enhanced_reports_enabled=True,
        knowledge_rag_enabled=True,
        chat_rag_enabled=True,
        _env_file=None,
    )
    client = TestClient(create_app(settings))

    response = client.get("/api/system/config-summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["paths"]["littlemodel_root"] == str(littlemodel_root)
    assert payload["paths"]["littlemodel_root_exists"] is True
    assert payload["integrations"]["deepseek_configured"] is True
    assert payload["integrations"]["qdrant_config_enabled"] is True
    assert payload["integrations"]["qdrant_enabled"] is True
    assert payload["integrations"]["qdrant_url_configured"] is True
    assert "qdrant_remote_available" in payload["integrations"]
    assert payload["features"]["enhanced_reports_enabled"] is True
    assert payload["features"]["qdrant_enabled"] is True
