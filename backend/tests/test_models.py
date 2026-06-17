from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.core.settings import Settings


def test_models_endpoint_returns_three_registered_models() -> None:
    client = TestClient(create_app())

    response = client.get("/api/models")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 3
    task_types = {model["task_type"] for model in payload["models"]}
    assert task_types == {"fault_diagnosis", "rul_prediction", "anomaly_detection"}
    for model in payload["models"]:
        assert model["model_id"]
        assert model["entrypoint"] == "inference.py:predict"
        assert model["status"] == "active"


def test_models_endpoint_returns_clear_error_when_registry_missing(tmp_path: Path) -> None:
    settings = Settings(littlemodel_root=tmp_path)
    client = TestClient(create_app(settings))

    response = client.get("/api/models")

    assert response.status_code == 500
    assert "Registry file does not exist" in response.json()["detail"]
