from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.main import create_app


LITTLEMODEL_ROOT = Path(__file__).resolve().parents[2] / "littlemodel"


def _client(tmp_path: Path) -> TestClient:
    return TestClient(
        create_app(
            Settings(
                backend_root=tmp_path,
                littlemodel_root=LITTLEMODEL_ROOT,
                agent_async_enabled=False,
            )
        )
    )


def _samples() -> list[Path]:
    return [
        LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy",
        LITTLEMODEL_ROOT / "rul_prediction" / "test_data" / "split_60_40" / "data-20130406T221209Z.mat",
        LITTLEMODEL_ROOT / "anomaly_detection" / "test_data" / "test_data_sample.csv",
    ]


def test_batch_diagnose_routes_each_file_and_persists_timelines(tmp_path: Path) -> None:
    client = _client(tmp_path)
    with ExitStack() as stack:
        files = [
            ("files", (path.name, stack.enter_context(path.open("rb"))))
            for path in _samples()
        ]
        response = client.post("/api/diagnose/batch", files=files)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["total"] == 3
    assert payload["succeeded"] == 3
    assert payload["failed"] == 0
    assert {item["task_type"] for item in payload["items"]} == {
        "fault_diagnosis",
        "rul_prediction",
        "anomaly_detection",
    }
    for item in payload["items"]:
        assert item["run_id"]
        assert item["case_id"]
        run = client.get(f"/api/agent-runs/{item['run_id']}")
        assert run.status_code == 200
        assert run.json()["run"]["case_id"] == item["case_id"]
        timeline = client.get(f"/api/agent-runs/{item['run_id']}/timeline")
        assert timeline.status_code == 200
        step_names = {entry["name"] for entry in timeline.json()["timeline"] if entry["kind"] == "step"}
        assert {"inspect_input", "classify_task", "execute_model", "persist_case"}.issubset(step_names)


def test_auto_diagnose_response_includes_persisted_run_id(tmp_path: Path) -> None:
    client = _client(tmp_path)
    sample = _samples()[0]
    with sample.open("rb") as handle:
        uploaded = client.post("/api/upload", files={"file": (sample.name, handle)})
    file_id = uploaded.json()["file"]["file_id"]

    response = client.post("/api/diagnose/auto", json={"file_id": file_id})

    assert response.status_code == 200
    run_id = response.json()["run_id"]
    detail = client.get(f"/api/agent-runs/{run_id}").json()["run"]
    assert detail["status"] == "succeeded"
    assert detail["case_id"] == response.json()["case_id"]
    assert [step["step_name"] for step in detail["steps"]] == [
        "inspect_input",
        "classify_task",
        "execute_model",
        "persist_case",
    ]
