from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.main import create_app


LITTLEMODEL_ROOT = Path(__file__).resolve().parents[2] / "littlemodel"


def _client(tmp_path: Path) -> TestClient:
    settings = Settings(
        backend_root=tmp_path,
        littlemodel_root=LITTLEMODEL_ROOT,
        agent_async_enabled=False,
    )
    return TestClient(create_app(settings))


def _upload(client: TestClient, path: Path) -> str:
    with path.open("rb") as handle:
        response = client.post("/api/upload", files={"file": (path.name, handle)})
    assert response.status_code == 200, response.text
    return response.json()["file"]["file_id"]


def test_auto_diagnose_routes_all_three_packaged_inputs(tmp_path: Path) -> None:
    client = _client(tmp_path)
    samples = [
        (
            "fault_diagnosis",
            LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy",
        ),
        (
            "rul_prediction",
            LITTLEMODEL_ROOT / "rul_prediction" / "test_data" / "split_60_40" / "data-20130406T221209Z.mat",
        ),
        (
            "anomaly_detection",
            LITTLEMODEL_ROOT / "anomaly_detection" / "test_data" / "test_data_sample.csv",
        ),
    ]

    for expected_task, sample_path in samples:
        file_id = _upload(client, sample_path)
        response = client.post("/api/diagnose/auto", json={"file_id": file_id})
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["status"] == "success"
        assert payload["task_type"] == expected_task
        assert payload["routing"]["status"] == "selected"
        assert payload["routing"]["selected_task_type"] == expected_task
        assert payload["routing"]["confidence"] >= 0.85
        assert payload["routing"]["evidence"]
        assert payload["selection_reason"].startswith("auto_task_classifier->")
        assert client.get(f"/api/cases/{payload['case_id']}").status_code == 200


def test_auto_diagnose_returns_candidates_for_ambiguous_csv(tmp_path: Path) -> None:
    client = _client(tmp_path)
    sample_path = tmp_path / "ambiguous.csv"
    sample_path.write_text("value\n1\n2\n3\n", encoding="utf-8")
    file_id = _upload(client, sample_path)

    response = client.post("/api/diagnose/auto", json={"file_id": file_id})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "needs_confirmation"
    assert payload["routing"]["selected_task_type"] is None
    assert len(payload["routing"]["candidates"]) == 3
    assert "case_id" not in payload


def test_auto_diagnose_returns_404_for_missing_file(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post("/api/diagnose/auto", json={"file_id": "missing-file"})

    assert response.status_code == 404
    assert "File metadata does not exist" in response.json()["detail"]
