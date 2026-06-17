from __future__ import annotations

from pathlib import Path
from time import sleep, time

from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.jobs.worker_runtime import AgentWorker
from app.main import create_app


LITTLEMODEL_ROOT = Path(r"C:\Users\luzian\Desktop\littlemodel")


def _create_client(tmp_path: Path, **overrides: object) -> TestClient:
    payload: dict[str, object] = {
        "backend_root": tmp_path,
        "littlemodel_root": LITTLEMODEL_ROOT,
        "agent_mode": "local",
        "deepseek_api_key": None,
        "knowledge_ingestion_enabled": True,
        "knowledge_rag_enabled": True,
        "chat_rag_enabled": True,
        "knowledge_case_ingestion_enabled": True,
        "enhanced_reports_enabled": True,
        "embedded_worker_enabled": True,
    }
    payload.update(overrides)
    settings = Settings(**payload)
    return TestClient(create_app(settings))


def _create_case(client: TestClient, task_type: str, path: Path) -> str:
    with path.open("rb") as handle:
        upload = client.post("/api/upload", files={"file": (path.name, handle)})
    file_id = upload.json()["file"]["file_id"]
    diagnose = client.post("/api/diagnose", json={"file_id": file_id, "task_type": task_type})
    return diagnose.json()["case_id"]


def _wait_for_run(client: TestClient, run_id: str, *, timeout_seconds: float = 20.0) -> dict[str, object]:
    deadline = time() + timeout_seconds
    while time() < deadline:
        response = client.get(f"/api/agent-runs/{run_id}")
        assert response.status_code == 200
        run = response.json()["run"]
        if run["status"] in {"succeeded", "failed", "cancelled"}:
            return run
        sleep(0.2)
    raise AssertionError(f"Timed out waiting for run {run_id}")


def test_async_chat_submission_completes_via_embedded_worker(tmp_path: Path) -> None:
    with _create_client(tmp_path) as client:
        case_id = _create_case(
            client,
            "fault_diagnosis",
            LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy",
        )

        response = client.post(
            "/api/agent-runs",
            json={
                "run_type": "chat_answer",
                "case_id": case_id,
                "input": {
                    "case_id": case_id,
                    "question": "请总结当前案例。",
                },
            },
        )

        assert response.status_code == 202
        run_id = response.json()["run_id"]
        run = _wait_for_run(client, run_id)
        assert run["status"] == "succeeded"
        assert run["output"]["answer"]
        assert run["job"]["status"] == "succeeded"


def test_async_enhanced_report_submission_completes_via_embedded_worker(tmp_path: Path) -> None:
    with _create_client(tmp_path) as client:
        case_id = _create_case(
            client,
            "fault_diagnosis",
            LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy",
        )

        response = client.post(
            "/api/agent-runs",
            json={
                "run_type": "enhanced_report",
                "case_id": case_id,
                "input": {"case_id": case_id},
            },
        )

        assert response.status_code == 202
        run_id = response.json()["run_id"]
        run = _wait_for_run(client, run_id)
        assert run["status"] == "succeeded"
        assert run["output"]["report_version_id"]
        assert run["job"]["status"] == "succeeded"


def test_queued_run_can_be_processed_later_by_manual_worker(tmp_path: Path) -> None:
    settings = Settings(
        backend_root=tmp_path,
        littlemodel_root=LITTLEMODEL_ROOT,
        agent_mode="local",
        deepseek_api_key=None,
        knowledge_ingestion_enabled=True,
        knowledge_rag_enabled=True,
        chat_rag_enabled=True,
        knowledge_case_ingestion_enabled=True,
        enhanced_reports_enabled=True,
        embedded_worker_enabled=False,
    )
    client = TestClient(create_app(settings))
    case_id = _create_case(
        client,
        "fault_diagnosis",
        LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy",
    )

    response = client.post(
        "/api/agent-runs",
        json={
            "run_type": "chat_answer",
            "case_id": case_id,
            "input": {
                "case_id": case_id,
                "question": "请解释当前结果。",
            },
        },
    )
    run_id = response.json()["run_id"]

    queued = client.get(f"/api/agent-runs/{run_id}")
    assert queued.status_code == 200
    assert queued.json()["run"]["status"] == "queued"
    assert queued.json()["run"]["steps"] == []

    worker = AgentWorker(settings, worker_id="manual-test")
    assert worker.process_next_job() is True

    completed = client.get(f"/api/agent-runs/{run_id}")
    assert completed.status_code == 200
    assert completed.json()["run"]["status"] == "succeeded"


def test_failed_or_cancelled_run_can_be_resumed(tmp_path: Path) -> None:
    settings = Settings(
        backend_root=tmp_path,
        littlemodel_root=LITTLEMODEL_ROOT,
        agent_mode="local",
        deepseek_api_key=None,
        embedded_worker_enabled=False,
    )
    client = TestClient(create_app(settings))
    case_id = "case-resume"

    response = client.post(
        "/api/agent-runs",
        json={
            "run_type": "chat_answer",
            "case_id": case_id,
            "input": {
                "case_id": case_id,
                "question": "这会失败，因为案例不存在。",
            },
        },
    )
    run_id = response.json()["run_id"]

    worker = AgentWorker(settings, worker_id="manual-fail")
    assert worker.process_next_job() is True

    failed = client.get(f"/api/agent-runs/{run_id}")
    assert failed.status_code == 200
    assert failed.json()["run"]["status"] == "failed"

    resumed = client.post(f"/api/agent-runs/{run_id}/resume")
    assert resumed.status_code == 200
    requeued = client.get(f"/api/agent-runs/{run_id}")
    assert requeued.json()["run"]["status"] == "queued"
