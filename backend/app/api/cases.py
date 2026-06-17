from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from app.core.case_store import CaseStoreError, CaseStoreService


router = APIRouter(tags=["cases"])


@router.get("/cases")
def list_cases(
    request: Request,
    task_type: Optional[str] = Query(default=None),
    risk_level: Optional[str] = Query(default=None),
) -> dict[str, object]:
    settings = request.app.state.settings
    service = CaseStoreService(settings.database_path)
    cases = service.list_cases(task_type=task_type, risk_level=risk_level)
    return {"status": "ok", "count": len(cases), "cases": cases}


@router.get("/cases/{case_id}")
def get_case(request: Request, case_id: str) -> dict[str, object]:
    settings = request.app.state.settings
    service = CaseStoreService(settings.database_path)
    try:
        case = service.get_case_detail(case_id)
    except CaseStoreError as exc:
        message = str(exc)
        status_code = 404 if message.startswith("Diagnosis case does not exist") else 500
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return {"status": "ok", "case": case}
