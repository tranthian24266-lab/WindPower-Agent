from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.main import create_app


LITTLEMODEL_ROOT = Path(r"C:\Users\luzian\Desktop\littlemodel")


def _create_auth_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        backend_root=tmp_path,
        littlemodel_root=LITTLEMODEL_ROOT,
        auth_enabled=True,
        api_key="secret-key",
        _env_file=None,
    )
    return TestClient(create_app(settings))


def test_health_endpoint_stays_open_when_auth_is_enabled(tmp_path: Path) -> None:
    client = _create_auth_client(tmp_path)

    response = client.get("/api/health")

    assert response.status_code == 200


def test_upload_requires_api_key_when_auth_is_enabled(tmp_path: Path) -> None:
    client = _create_auth_client(tmp_path)

    response = client.post(
        "/api/upload",
        files={"file": ("sample.csv", b"col1,col2\n1,2\n", "text/csv")},
    )

    assert response.status_code == 401
    assert "Missing or invalid API key" in response.json()["detail"]


def test_upload_accepts_valid_api_key_when_auth_is_enabled(tmp_path: Path) -> None:
    client = _create_auth_client(tmp_path)

    response = client.post(
        "/api/upload",
        headers={"X-API-Key": "secret-key"},
        files={"file": ("sample.csv", b"col1,col2\n1,2\n", "text/csv")},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_diagnose_requires_api_key_when_auth_is_enabled(tmp_path: Path) -> None:
    client = _create_auth_client(tmp_path)
    upload = client.post(
        "/api/upload",
        headers={"X-API-Key": "secret-key"},
        files={
            "file": (
                "test_sensor1_x.npy",
                (LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy").read_bytes(),
                "application/octet-stream",
            )
        },
    )
    assert upload.status_code == 200
    file_id = upload.json()["file"]["file_id"]

    response = client.post("/api/diagnose", json={"file_id": file_id, "task_type": "fault_diagnosis"})

    assert response.status_code == 401
    assert "Missing or invalid API key" in response.json()["detail"]


def test_review_endpoint_requires_reviewer_role_when_rbac_enabled(tmp_path: Path) -> None:
    settings = Settings(
        backend_root=tmp_path,
        littlemodel_root=LITTLEMODEL_ROOT,
        auth_enabled=True,
        api_key="secret-key",
        rbac_enabled=True,
        _env_file=None,
    )
    client = TestClient(create_app(settings))

    forbidden = client.post(
        "/api/reviews/dummy-review/approve",
        headers={"X-API-Key": "secret-key", "X-Actor-Role": "operator", "X-Actor-Id": "ops-a"},
        json={"reviewer": "ops-a", "comment": "not allowed"},
    )
    assert forbidden.status_code == 403

    allowed = client.post(
        "/api/reviews/dummy-review/approve",
        headers={"X-API-Key": "secret-key", "X-Actor-Role": "reviewer", "X-Actor-Id": "qa-a"},
        json={"reviewer": "qa-a", "comment": "approved"},
    )
    assert allowed.status_code == 404
