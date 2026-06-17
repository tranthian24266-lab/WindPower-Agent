from __future__ import annotations

from pathlib import Path

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
    }
    payload.update(overrides)
    settings = Settings(**payload)
    return TestClient(create_app(settings))


def test_eval_api_lists_three_suites_and_runs_one(tmp_path: Path) -> None:
    client = _create_client(tmp_path)

    suites = client.get("/api/evals/suites")

    assert suites.status_code == 200
    suite_ids = {item["suite_id"] for item in suites.json()["suites"]}
    assert {"fault_diagnosis_smoke", "rul_prediction_smoke", "anomaly_report_smoke"} <= suite_ids

    run_response = client.post("/api/evals/run", json={"suite_id": "fault_diagnosis_smoke"})

    assert run_response.status_code == 200
    eval_run = run_response.json()["eval_run"]
    assert eval_run["suite_id"] == "fault_diagnosis_smoke"
    assert eval_run["total_count"] == 1
    assert eval_run["items"][0]["status"] in {"passed", "failed"}

    listed = client.get("/api/evals")
    assert listed.status_code == 200
    assert listed.json()["runs"][0]["eval_run_id"] == eval_run["eval_run_id"]

    detail = client.get(f"/api/evals/{eval_run['eval_run_id']}")
    assert detail.status_code == 200
    assert detail.json()["eval_run"]["items"][0]["details"]["suite_id"] == "fault_diagnosis_smoke"


def test_eval_run_logs_summary_and_observability_summary_exposes_counts(tmp_path: Path) -> None:
    client = _create_client(tmp_path)

    run_response = client.post("/api/evals/run", json={"suite_id": "anomaly_report_smoke"})

    assert run_response.status_code == 200
    observability = client.get("/api/system/observability-summary")
    assert observability.status_code == 200
    payload = observability.json()
    assert payload["event_count"] >= 1
    assert payload["counts_by_type"].get("eval_run_summary", 0) >= 1
