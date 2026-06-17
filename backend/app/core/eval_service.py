from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.agent_service import AgentService
from app.core.case_store import CaseStoreService
from app.core.enhanced_report_service import EnhancedReportService
from app.core.file_manager import FileManagerService
from app.core.model_runner import ModelRunnerService
from app.core.settings import Settings
from app.core.telemetry_service import TelemetryService
from app.db.database import Database


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class EvalServiceError(RuntimeError):
    """Raised when an eval suite cannot be executed safely."""


class EvalService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.database = Database(settings.database_path)
        self.database.initialize()
        self.file_manager = FileManagerService(settings.uploads_path)
        self.case_store = CaseStoreService(settings.database_path)
        self.runner = ModelRunnerService(settings)
        self.agent_service = AgentService(settings)
        self.enhanced_report_service = EnhancedReportService(settings)
        self.telemetry = TelemetryService(settings)

    def list_suites(self) -> list[dict[str, Any]]:
        suites: list[dict[str, Any]] = []
        for path in sorted(self.settings.eval_suites_path.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["item_count"] = len(payload.get("items") or [])
            suites.append(payload)
        return suites

    def run_suite(self, suite_id: str) -> dict[str, Any]:
        suite = self._load_suite(suite_id)
        eval_run_id = uuid4().hex
        now = _utcnow()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO eval_runs (
                    eval_run_id, suite_id, suite_version, status, score,
                    passed_count, failed_count, total_count, summary_json, metadata_json, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    eval_run_id,
                    suite["suite_id"],
                    suite["version"],
                    "running",
                    None,
                    0,
                    0,
                    len(suite.get("items") or []),
                    None,
                    self._dump_json({"title": suite.get("title"), "description": suite.get("description")}),
                    now,
                    None,
                ),
            )

        item_results: list[dict[str, Any]] = []
        for item in suite.get("items") or []:
            result = self._run_item(eval_run_id, suite, item)
            item_results.append(result)

        passed_count = sum(1 for item in item_results if item["status"] == "passed")
        failed_count = len(item_results) - passed_count
        score = round(passed_count / len(item_results), 4) if item_results else 0.0
        summary = {
            "suite_id": suite["suite_id"],
            "suite_version": suite["version"],
            "title": suite.get("title"),
            "description": suite.get("description"),
            "score": score,
            "passed_count": passed_count,
            "failed_count": failed_count,
            "total_count": len(item_results),
        }
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE eval_runs
                SET status = ?, score = ?, passed_count = ?, failed_count = ?, total_count = ?,
                    summary_json = ?, finished_at = ?
                WHERE eval_run_id = ?
                """,
                (
                    "succeeded" if failed_count == 0 else "failed",
                    score,
                    passed_count,
                    failed_count,
                    len(item_results),
                    self._dump_json(summary),
                    _utcnow(),
                    eval_run_id,
                ),
            )

        self.telemetry.record(
            "eval_run_summary",
            {
                "eval_run_id": eval_run_id,
                "suite_id": suite["suite_id"],
                "suite_version": suite["version"],
                "score": score,
                "passed_count": passed_count,
                "failed_count": failed_count,
                "total_count": len(item_results),
            },
        )
        return self.get_run(eval_run_id)

    def list_runs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM eval_runs
                ORDER BY started_at DESC, eval_run_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._deserialize_eval_run(dict(row)) for row in rows]

    def get_run(self, eval_run_id: str) -> dict[str, Any]:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM eval_runs WHERE eval_run_id = ?", (eval_run_id,)).fetchone()
            if row is None:
                raise EvalServiceError(f"Eval run does not exist for eval_run_id '{eval_run_id}'.")
            item_rows = connection.execute(
                "SELECT * FROM eval_run_items WHERE eval_run_id = ? ORDER BY created_at ASC, eval_item_id ASC",
                (eval_run_id,),
            ).fetchall()
        payload = self._deserialize_eval_run(dict(row))
        payload["items"] = [self._deserialize_eval_item(dict(item)) for item in item_rows]
        return payload

    def _load_suite(self, suite_id: str) -> dict[str, Any]:
        path = self.settings.eval_suites_path / f"{suite_id}.json"
        if not path.exists():
            raise EvalServiceError(f"Eval suite does not exist for suite_id '{suite_id}'.")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise EvalServiceError(f"Eval suite '{suite_id}' has invalid structure.")
        return payload

    def _run_item(self, eval_run_id: str, suite: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
        sample_path = self.settings.resolved_littlemodel_root / str(item["sample_path"])
        file_meta = self.file_manager.import_local_file(sample_path)
        self.case_store.save_uploaded_file(file_meta)
        diagnosis = self.runner.run_diagnosis(file_meta["file_id"], str(item["task_type"]), None)
        self.case_store.save_diagnosis_case(diagnosis)

        checks: list[dict[str, Any]] = []
        checks.append({"name": "diagnosis_status_ok", "passed": diagnosis.get("status") == "ok"})
        if item["task_type"] == "rul_prediction":
            checks.append({"name": "rul_raw_present", "passed": diagnosis["result"].get("rul_raw") is not None})
            checks.append({"name": "rul_clipped_present", "passed": diagnosis["result"].get("rul_clipped") is not None})
        else:
            checks.append({"name": "risk_level_present", "passed": bool(diagnosis.get("risk_level"))})

        chat_payload: dict[str, Any] | None = None
        if item.get("chat_question"):
            chat_payload = self.agent_service.answer(diagnosis["case_id"], str(item["chat_question"]))
            checks.append({"name": "chat_answer_non_empty", "passed": bool(str(chat_payload.get("answer") or "").strip())})

        report_payload: dict[str, Any] | None = None
        if item.get("generate_enhanced_report"):
            report_payload = self.enhanced_report_service.generate(diagnosis["case_id"])
            checks.append({"name": "report_version_created", "passed": bool(report_payload.get("report_version_id"))})
            checks.append(
                {
                    "name": "report_status_reviewable",
                    "passed": str(report_payload.get("report_status") or "") in {"ready", "waiting_review"},
                }
            )

        passed = all(check["passed"] for check in checks)
        details = {
            "suite_id": suite["suite_id"],
            "suite_version": suite["version"],
            "item_key": item["item_key"],
            "case_id": diagnosis["case_id"],
            "task_type": item["task_type"],
            "checks": checks,
            "diagnosis": {
                "status": diagnosis.get("status"),
                "risk_level": diagnosis.get("risk_level"),
                "model_id": diagnosis.get("model_id"),
            },
            "chat": {"mode": chat_payload.get("mode"), "has_answer": bool(chat_payload.get("answer"))} if chat_payload else None,
            "enhanced_report": {
                "report_version_id": report_payload.get("report_version_id"),
                "report_status": report_payload.get("report_status"),
                "source_mode": report_payload.get("source_mode"),
            }
            if report_payload
            else None,
        }
        eval_item_id = uuid4().hex
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO eval_run_items (
                    eval_item_id, eval_run_id, item_key, status, score, details_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    eval_item_id,
                    eval_run_id,
                    str(item["item_key"]),
                    "passed" if passed else "failed",
                    1.0 if passed else 0.0,
                    self._dump_json(details),
                    _utcnow(),
                ),
            )
        return {"eval_item_id": eval_item_id, "status": "passed" if passed else "failed", "score": 1.0 if passed else 0.0}

    def _deserialize_eval_run(self, row: dict[str, Any]) -> dict[str, Any]:
        row["summary"] = self._load_json(row.pop("summary_json", None))
        row["metadata"] = self._load_json(row.pop("metadata_json", None))
        return row

    def _deserialize_eval_item(self, row: dict[str, Any]) -> dict[str, Any]:
        row["details"] = self._load_json(row.pop("details_json", None))
        return row

    def _dump_json(self, payload: dict[str, Any] | None) -> str | None:
        if payload is None:
            return None
        return json.dumps(payload, ensure_ascii=False)

    def _load_json(self, raw: str | None) -> dict[str, Any] | None:
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}
        return parsed if isinstance(parsed, dict) else {"value": parsed}
