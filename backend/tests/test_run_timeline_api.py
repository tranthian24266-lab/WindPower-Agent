from __future__ import annotations

from pathlib import Path
from time import sleep, time

from fastapi.testclient import TestClient

from app.core.settings import Settings
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


def _create_case(client: TestClient) -> str:
    sample = LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy"
    with sample.open("rb") as handle:
        upload = client.post("/api/upload", files={"file": (sample.name, handle)})
    file_id = upload.json()["file"]["file_id"]
    diagnose = client.post("/api/diagnose", json={"file_id": file_id, "task_type": "fault_diagnosis"})
    return diagnose.json()["case_id"]


def _wait_for_run(client: TestClient, run_id: str, *, timeout_seconds: float = 20.0) -> dict[str, object]:
    deadline = time() + timeout_seconds
    while time() < deadline:
        response = client.get(f"/api/agent-runs/{run_id}")
        assert response.status_code == 200
        run = response.json()["run"]
        if run["status"] in {"succeeded", "failed", "cancelled", "waiting_review"}:
            return run
        sleep(0.2)
    raise AssertionError(f"Timed out waiting for run {run_id}")


def test_run_timeline_returns_trace_id_steps_and_telemetry(tmp_path: Path) -> None:
    with _create_client(tmp_path) as client:
        case_id = _create_case(client)
        response = client.post(
            "/api/agent-runs",
            json={
                "run_type": "chat_answer",
                "case_id": case_id,
                "input": {"case_id": case_id, "question": "请总结当前结果。"},
            },
        )
        assert response.status_code == 202
        run_id = response.json()["run_id"]
        run = _wait_for_run(client, run_id)
        assert run["trace_id"]

        timeline = client.get(f"/api/agent-runs/{run_id}/timeline")
        assert timeline.status_code == 200
        payload = timeline.json()
        assert payload["trace_id"] == run["trace_id"]
        assert len(payload["timeline"]) >= 3
        names = {item["name"] for item in payload["timeline"]}
        assert "run.started" in names
        assert any(name.startswith("step:") or name == "chat.answer" for name in names)
        telemetry_names = {item["name"] for item in payload["timeline"] if item["kind"] == "telemetry"}
        assert "trace_span" in telemetry_names or "chat_answer_summary" in telemetry_names
