from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from app.core.auto_diagnosis_service import AutoDiagnosisService
from app.core.auth import get_actor_context, require_write_api_key
from app.core.case_store import CaseStoreService
from app.core.file_manager import FileManagerError, FileManagerService
from app.core.input_profiler import InputProfileError
from app.core.model_router import ModelRouterError
from app.core.model_registry import ModelRegistryError
from app.core.model_runner import ModelRunnerError, ModelRunnerService
from app.db.schemas import AutoDiagnoseRequest, DiagnoseRequest


router = APIRouter(tags=["diagnosis"])


@router.post("/diagnose", dependencies=[Depends(require_write_api_key)])
def diagnose(request: Request, payload: DiagnoseRequest) -> dict[str, object]:
    settings = request.app.state.settings
    runner = ModelRunnerService(settings)
    store = CaseStoreService(settings.database_path)
    try:
        result = runner.run_diagnosis(payload.file_id, payload.task_type, payload.options)
    except FileManagerError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ModelRegistryError, ModelRouterError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ModelRunnerError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    store.save_diagnosis_case(result)
    return result


@router.post("/diagnose/auto", dependencies=[Depends(require_write_api_key)])
def auto_diagnose(request: Request, payload: AutoDiagnoseRequest) -> dict[str, object]:
    actor = get_actor_context(request)
    try:
        return AutoDiagnosisService(request.app.state.settings).execute(
            payload.file_id,
            confirmed_task_type=payload.confirmed_task_type,
            options=payload.options,
            triggered_by=actor.actor_id,
        )
    except FileManagerError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (InputProfileError, ModelRegistryError, ModelRouterError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ModelRunnerError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/diagnose/batch", dependencies=[Depends(require_write_api_key)])
async def batch_diagnose(
    request: Request,
    files: list[UploadFile] = File(...),
) -> dict[str, object]:
    if not files:
        raise HTTPException(status_code=400, detail="At least one input file is required.")
    if len(files) > 50:
        raise HTTPException(status_code=400, detail="A batch can contain at most 50 files.")

    settings = request.app.state.settings
    actor = get_actor_context(request)
    file_manager = FileManagerService(settings.uploads_path)
    store = CaseStoreService(settings.database_path)
    service = AutoDiagnosisService(settings)
    batch_id = uuid4().hex
    items: list[dict[str, object]] = []
    for upload in files:
        filename = upload.filename or "unnamed"
        try:
            metadata = await file_manager.save_upload(upload)
            store.save_uploaded_file(metadata)
            result = service.execute(metadata["file_id"], triggered_by=actor.actor_id)
            items.append(
                {
                    "filename": filename,
                    "file_id": metadata["file_id"],
                    "status": result["status"],
                    "run_id": result.get("run_id"),
                    "case_id": result.get("case_id"),
                    "task_type": result.get("task_type") or result.get("routing", {}).get("selected_task_type"),
                    "model_id": result.get("model_id"),
                    "routing": result.get("routing"),
                }
            )
        except Exception as exc:
            items.append(
                {
                    "filename": filename,
                    "status": "failed",
                    "error": {"type": type(exc).__name__, "message": str(exc)},
                }
            )
    succeeded = sum(1 for item in items if item["status"] == "success")
    needs_confirmation = sum(1 for item in items if item["status"] == "needs_confirmation")
    failed = len(items) - succeeded - needs_confirmation
    return {
        "status": "completed" if failed == 0 else "partial",
        "batch_id": batch_id,
        "total": len(items),
        "succeeded": succeeded,
        "needs_confirmation": needs_confirmation,
        "failed": failed,
        "items": items,
    }
