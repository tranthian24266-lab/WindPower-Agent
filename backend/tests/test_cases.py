from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.core.settings import Settings


LITTLEMODEL_ROOT = Path(r"C:\Users\luzian\Desktop\littlemodel")


def _create_client(tmp_path: Path) -> TestClient:
    settings = Settings(backend_root=tmp_path, littlemodel_root=LITTLEMODEL_ROOT)
    return TestClient(create_app(settings))


def _upload_and_diagnose(client: TestClient, task_type: str, path: Path) -> dict:
    with path.open("rb") as handle:
        upload = client.post("/api/upload", files={"file": (path.name, handle)})
    file_id = upload.json()["file"]["file_id"]
    diagnose = client.post("/api/diagnose", json={"file_id": file_id, "task_type": task_type})
    assert diagnose.status_code == 200
    return diagnose.json()


def test_cases_list_and_detail(tmp_path: Path) -> None:
    client = _create_client(tmp_path)
    fault = _upload_and_diagnose(client, "fault_diagnosis", LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy")
    _upload_and_diagnose(
        client,
        "rul_prediction",
        LITTLEMODEL_ROOT / "rul_prediction" / "test_data" / "split_60_40" / "data-20130406T221209Z.mat",
    )
    _upload_and_diagnose(client, "anomaly_detection", LITTLEMODEL_ROOT / "anomaly_detection" / "test_data" / "test_data_sample.csv")

    response = client.get("/api/cases")
    assert response.status_code == 200
    assert response.json()["count"] == 3

    filtered = client.get("/api/cases", params={"task_type": "rul_prediction"})
    assert filtered.status_code == 200
    assert filtered.json()["count"] == 1

    detail = client.get(f"/api/cases/{fault['case_id']}")
    assert detail.status_code == 200
    payload = detail.json()["case"]
    assert payload["case_id"] == fault["case_id"]
    assert payload["result"]["task_type"] == "fault_diagnosis"
    assert payload["model_version_id"] == "model_version::nrel_binary_mscnn_bilstm_sensor1"
    assert payload["model_alias"] == "default"
    assert payload["selection_reason"] == "task_type_default_alias:default"


def test_case_detail_returns_clear_error_when_result_missing(tmp_path: Path) -> None:
    client = _create_client(tmp_path)
    case = _upload_and_diagnose(client, "fault_diagnosis", LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy")
    Path(case["result_json_path"]).unlink()

    response = client.get(f"/api/cases/{case['case_id']}")

    assert response.status_code == 500
    assert "Result file does not exist" in response.json()["detail"]
