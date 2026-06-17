from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.audit_service import AuditService
from app.core.auth import get_actor_context, require_permissions
from app.core.eval_service import EvalService, EvalServiceError


router = APIRouter(tags=["evals"])


@router.get("/evals/suites")
def list_eval_suites(request: Request) -> dict[str, object]:
    service = EvalService(request.app.state.settings)
    suites = service.list_suites()
    return {"status": "ok", "count": len(suites), "suites": suites}


@router.post("/evals/run", dependencies=[Depends(require_permissions("evals:run"))])
def run_eval_suite(request: Request, payload: dict[str, object]) -> dict[str, object]:
    suite_id = str(payload.get("suite_id") or "").strip()
    if not suite_id:
        raise HTTPException(status_code=400, detail="suite_id is required.")
    service = EvalService(request.app.state.settings)
    actor = get_actor_context(request)
    try:
        result = service.run_suite(suite_id)
        AuditService(request.app.state.settings).record(
            actor=actor,
            action="eval.run",
            resource_type="eval_suite",
            resource_id=suite_id,
            details={"eval_run_id": result.get("eval_run_id"), "suite_id": suite_id},
        )
        return {"status": "ok", "eval_run": result}
    except EvalServiceError as exc:
        message = str(exc)
        status_code = 404 if "does not exist" in message else 500
        raise HTTPException(status_code=status_code, detail=message) from exc


@router.get("/evals")
def list_eval_runs(request: Request, limit: int = Query(default=50, ge=1, le=200)) -> dict[str, object]:
    service = EvalService(request.app.state.settings)
    runs = service.list_runs(limit=limit)
    return {"status": "ok", "count": len(runs), "runs": runs}


@router.get("/evals/{eval_run_id}")
def get_eval_run(request: Request, eval_run_id: str) -> dict[str, object]:
    service = EvalService(request.app.state.settings)
    try:
        payload = service.get_run(eval_run_id)
    except EvalServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "ok", "eval_run": payload}
