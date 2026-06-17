from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.core.settings import Settings


LITTLEMODEL_ROOT = Path(r"C:\Users\luzian\Desktop\littlemodel")


def _create_client(tmp_path: Path) -> TestClient:
    settings = Settings(backend_root=tmp_path, littlemodel_root=LITTLEMODEL_ROOT)
    return TestClient(create_app(settings))


def _upload(client: TestClient, path: Path) -> str:
    with path.open("rb") as handle:
        response = client.post("/api/upload", files={"file": (path.name, handle)})
    assert response.status_code == 200
    return response.json()["file"]["file_id"]


def test_diagnose_fault_model(tmp_path: Path) -> None:
    client = _create_client(tmp_path)
    file_id = _upload(client, LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy")

    response = client.post("/api/diagnose", json={"file_id": file_id, "task_type": "fault_diagnosis"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["task_type"] == "fault_diagnosis"
    assert payload["model_version_id"] == "model_version::nrel_binary_mscnn_bilstm_sensor1"
    assert payload["model_alias"] == "default"
    assert payload["selection_reason"] == "task_type_default_alias:default"
    assert Path(payload["result_json_path"]).exists()


def test_diagnose_rul_model(tmp_path: Path) -> None:
    client = _create_client(tmp_path)
    file_id = _upload(
        client,
        LITTLEMODEL_ROOT / "rul_prediction" / "test_data" / "split_60_40" / "data-20130406T221209Z.mat",
    )

    response = client.post("/api/diagnose", json={"file_id": file_id, "task_type": "rul_prediction"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["task_type"] == "rul_prediction"
    assert Path(payload["result_json_path"]).exists()


def test_diagnose_anomaly_model(tmp_path: Path) -> None:
    client = _create_client(tmp_path)
    file_id = _upload(client, LITTLEMODEL_ROOT / "anomaly_detection" / "test_data" / "test_data_sample.csv")

    response = client.post("/api/diagnose", json={"file_id": file_id, "task_type": "anomaly_detection"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["task_type"] == "anomaly_detection"
    assert Path(payload["result_json_path"]).exists()


def test_diagnose_returns_clear_error_for_bad_task_type(tmp_path: Path) -> None:
    client = _create_client(tmp_path)
    file_id = _upload(client, LITTLEMODEL_ROOT / "anomaly_detection" / "test_data" / "test_data_sample.csv")

    response = client.post("/api/diagnose", json={"file_id": file_id, "task_type": "bad_task"})

    assert response.status_code == 400
    assert "No active model found" in response.json()["detail"]


def test_diagnose_returns_clear_error_for_missing_file(tmp_path: Path) -> None:
    client = _create_client(tmp_path)

    response = client.post("/api/diagnose", json={"file_id": "missing-file", "task_type": "fault_diagnosis"})

    assert response.status_code == 404
    assert "File metadata does not exist" in response.json()["detail"]


def test_diagnose_honors_preferred_model_id_and_persists_routing_trace(tmp_path: Path) -> None:
    client = _create_client(tmp_path)
    file_id = _upload(client, LITTLEMODEL_ROOT / "anomaly_detection" / "test_data" / "test_data_sample.csv")

    response = client.post(
        "/api/diagnose",
        json={
            "file_id": file_id,
            "task_type": "anomaly_detection",
            "options": {
                "preferred_model_id": "scada_ae_decoder_transfer_13_to_10",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["model_id"] == "scada_ae_decoder_transfer_13_to_10"
    assert payload["selection_reason"] == "preferred_model_id"

    detail = client.get(f"/api/cases/{payload['case_id']}")
    assert detail.status_code == 200
    case_payload = detail.json()["case"]
    assert case_payload["model_id"] == "scada_ae_decoder_transfer_13_to_10"
    assert case_payload["selection_reason"] == "preferred_model_id"
