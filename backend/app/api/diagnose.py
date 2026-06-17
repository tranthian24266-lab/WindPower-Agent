from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.auth import require_write_api_key
from app.core.case_store import CaseStoreService
from app.core.file_manager import FileManagerError
from app.core.model_router import ModelRouterError
from app.core.model_registry import ModelRegistryError
from app.core.model_runner import ModelRunnerError, ModelRunnerService
from app.db.schemas import DiagnoseRequest


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
    except ModelRegistryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ModelRouterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ModelRunnerError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    store.save_diagnosis_case(result)

    return result
