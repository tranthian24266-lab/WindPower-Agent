from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.core.settings import Settings


LITTLEMODEL_ROOT = Path(r"C:\Users\luzian\Desktop\littlemodel")


def test_upload_and_fetch_metadata(tmp_path: Path) -> None:
    settings = Settings(backend_root=tmp_path, littlemodel_root=LITTLEMODEL_ROOT)
    client = TestClient(create_app(settings))

    response = client.post(
        "/api/upload",
        files={"file": ("sample.csv", b"col1,col2\n1,2\n", "text/csv")},
    )

    assert response.status_code == 200
    payload = response.json()["file"]
    file_id = payload["file_id"]
    stored_path = Path(payload["stored_path"])
    assert stored_path.exists()

    detail_response = client.get(f"/api/files/{file_id}")

    assert detail_response.status_code == 200
    assert detail_response.json()["file"]["original_filename"] == "sample.csv"


def test_upload_rejects_unsupported_extension(tmp_path: Path) -> None:
    settings = Settings(backend_root=tmp_path, littlemodel_root=LITTLEMODEL_ROOT)
    client = TestClient(create_app(settings))

    response = client.post(
        "/api/upload",
        files={"file": ("sample.txt", b"plain text", "text/plain")},
    )

    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]
