from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any

from app.core.agent_runtime.run_manager import RunManager
from app.core.case_store import CaseStoreService
from app.core.file_manager import FileManagerService
from app.core.model_runner import ModelRunnerService
from app.core.settings import Settings
from app.core.task_classifier import TaskClassifierService


class AutoDiagnosisService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.files = FileManagerService(settings.uploads_path)
        self.runner = ModelRunnerService(settings)
        self.store = CaseStoreService(settings.database_path)
        self.runs = RunManager(settings.database_path)
        self.classifier = TaskClassifierService(settings.resolved_littlemodel_root)

    def execute(
        self,
        file_id: str,
        *,
        confirmed_task_type: str | None = None,
        options: dict[str, Any] | None = None,
        triggered_by: str | None = None,
    ) -> dict[str, Any]:
        run_id = self.runs.create_run(
            run_type="auto_diagnosis",
            input_payload={"file_id": file_id, "confirmed_task_type": confirmed_task_type},
            triggered_by=triggered_by,
        )
        self.runs.mark_running(run_id, current_step="inspect_input")
        current_step_id: str | None = None
        try:
            current_step_id = self.runs.start_step(
                run_id=run_id,
                step_name="inspect_input",
                step_type="analysis",
                input_payload={"file_id": file_id},
            )
            started = perf_counter()
            file_meta = self.files.get_file_metadata(file_id)
            classification = self.classifier.classify(Path(str(file_meta["stored_path"])))
            routing = classification.as_dict()
            self.runs.complete_step(
                current_step_id,
                output_payload={"input_profile": routing["input_profile"]},
                duration_ms=_elapsed_ms(started),
            )

            current_step_id = self.runs.start_step(
                run_id=run_id,
                step_name="classify_task",
                step_type="routing",
                input_payload={"candidates": routing["candidates"]},
            )
            task_type = confirmed_task_type or classification.selected_task_type
            if confirmed_task_type:
                candidate = next(
                    (item for item in classification.candidates if item.task_type == confirmed_task_type),
                    None,
                )
                if candidate is None or candidate.score < 0.35:
                    raise ValueError("Confirmed task type is not compatible with this input.")
                routing.update(
                    status="confirmed",
                    selected_task_type=confirmed_task_type,
                    selected_model_id=candidate.model_id,
                )
            self.runs.complete_step(current_step_id, output_payload=routing)
            if task_type is None:
                response = {"status": classification.status, "file_id": file_id, "routing": routing, "run_id": run_id}
                if classification.status == "needs_confirmation":
                    self.runs.mark_waiting_review(run_id, output_payload=response, current_step="classify_task")
                else:
                    self.runs.complete_run(run_id, output_payload=response, current_step="classify_task")
                return response

            current_step_id = self.runs.start_step(
                run_id=run_id,
                step_name="execute_model",
                step_type="model_inference",
                input_payload={"task_type": task_type, "selected_model_id": routing.get("selected_model_id")},
            )
            started = perf_counter()
            result = self.runner.run_diagnosis(file_id, task_type, options)
            result["selection_reason"] = f"auto_task_classifier->{result.get('selection_reason') or 'model_router'}"
            result["routing"] = routing
            result["run_id"] = run_id
            self.runs.complete_step(
                current_step_id,
                output_payload={
                    "case_id": result["case_id"],
                    "model_id": result["model_id"],
                    "model_version_id": result.get("model_version_id"),
                    "status": result["status"],
                },
                duration_ms=_elapsed_ms(started),
            )

            current_step_id = self.runs.start_step(
                run_id=run_id,
                step_name="persist_case",
                step_type="persistence",
                input_payload={"case_id": result["case_id"]},
            )
            self.store.save_diagnosis_case(result)
            self.runs.complete_step(current_step_id, output_payload={"case_id": result["case_id"]})
            self.runs.complete_run(
                run_id,
                case_id=result["case_id"],
                output_payload={
                    "case_id": result["case_id"],
                    "task_type": result["task_type"],
                    "model_id": result["model_id"],
                },
                current_step="persist_case",
            )
            return result
        except Exception as exc:
            error = {"type": type(exc).__name__, "message": str(exc)}
            if current_step_id:
                self.runs.fail_step(current_step_id, error_payload=error)
            self.runs.fail_run(run_id, error_payload=error, current_step="failed")
            raise


def _elapsed_ms(started: float) -> int:
    return max(0, int((perf_counter() - started) * 1000))
