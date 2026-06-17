from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.core.agent_runtime.run_manager import RunManager
from app.core.audit_service import AuditService
from app.core.auth import get_actor_context, require_permissions
from app.core.telemetry_service import TelemetryService
from app.db.schemas import AgentRunCreateRequest


router = APIRouter(tags=["agent-runs"])

SUPPORTED_RUN_TYPES = {"chat_answer", "enhanced_report"}


@router.post("/agent-runs", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_permissions("agent_run:create"))])
def create_agent_run(request: Request, payload: AgentRunCreateRequest) -> dict[str, object]:
    settings = request.app.state.settings
    actor = get_actor_context(request)
    if not settings.agent_async_enabled:
        raise HTTPException(status_code=409, detail="Agent async execution is disabled.")
    if payload.run_type not in SUPPORTED_RUN_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported run_type: {payload.run_type}")

    normalized_input = dict(payload.input or {})
    case_id = payload.case_id or normalized_input.get("case_id")
    session_id = payload.session_id or normalized_input.get("session_id")
    if payload.run_type == "chat_answer":
        if not case_id:
            raise HTTPException(status_code=400, detail="chat_answer requires case_id.")
        if not str(normalized_input.get("question") or "").strip():
            raise HTTPException(status_code=400, detail="chat_answer requires input.question.")
        normalized_input.setdefault("case_id", case_id)
        if session_id:
            normalized_input.setdefault("session_id", session_id)
    elif payload.run_type == "enhanced_report":
        if not case_id:
            raise HTTPException(status_code=400, detail="enhanced_report requires case_id.")
        normalized_input = {"case_id": case_id}

    manager = RunManager(settings.database_path)
    run_id = manager.create_run(
        run_type=payload.run_type,
        case_id=case_id,
        session_id=session_id,
        input_payload=normalized_input,
        triggered_by=actor.actor_id,
    )
    job_id = manager.enqueue_job(
        run_id=run_id,
        job_type=payload.run_type,
        payload=normalized_input,
        max_attempts=settings.worker_max_attempts,
    )
    AuditService(settings).record(
        actor=actor,
        action="agent_run.create",
        resource_type="agent_run",
        resource_id=run_id,
        run_id=run_id,
        trace_id=(manager.get_run_detail(run_id) or {}).get("trace_id"),
        details={"run_type": payload.run_type, "case_id": case_id, "job_id": job_id},
    )
    return {
        "status": "accepted",
        "run_id": run_id,
        "job_id": job_id,
        "run_type": payload.run_type,
        "case_id": case_id,
        "session_id": session_id,
        "poll_url": f"/api/agent-runs/{run_id}",
    }


@router.get("/agent-runs")
def list_agent_runs(
    request: Request,
    case_id: Optional[str] = Query(default=None),
    run_type: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, object]:
    manager = RunManager(request.app.state.settings.database_path)
    runs = manager.list_runs(case_id=case_id, run_type=run_type, limit=limit)
    return {"status": "ok", "count": len(runs), "runs": runs}


@router.get("/agent-runs/{run_id}")
def get_agent_run(request: Request, run_id: str) -> dict[str, object]:
    manager = RunManager(request.app.state.settings.database_path)
    payload = manager.get_run_detail(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Agent run does not exist for run_id '{run_id}'.")
    return {"status": "ok", "run": payload}


@router.get("/agent-runs/{run_id}/timeline")
def get_agent_run_timeline(request: Request, run_id: str) -> dict[str, object]:
    settings = request.app.state.settings
    manager = RunManager(settings.database_path)
    payload = manager.get_run_detail(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Agent run does not exist for run_id '{run_id}'.")
    telemetry = TelemetryService(settings)
    telemetry_events = telemetry.list_events(
        run_id=run_id,
        trace_id=str(payload.get("trace_id") or "") or None,
        limit=200,
    )
    timeline: list[dict[str, object]] = [
        {
            "timestamp": payload["started_at"],
            "kind": "run",
            "name": "run.started",
            "status": payload["status"],
            "details": {"run_type": payload["run_type"], "trace_id": payload.get("trace_id")},
        }
    ]
    for step in payload.get("steps") or []:
        timeline.append(
            {
                "timestamp": step["started_at"],
                "kind": "step",
                "name": step["step_name"],
                "status": step["status"],
                "details": {"step_type": step["step_type"], "duration_ms": step.get("duration_ms")},
            }
        )
        for tool_call in step.get("tool_calls") or []:
            timeline.append(
                {
                    "timestamp": tool_call["created_at"],
                    "kind": "tool_call",
                    "name": tool_call["tool_name"],
                    "status": tool_call["status"],
                    "details": {"duration_ms": tool_call.get("duration_ms"), "tool_version": tool_call.get("tool_version")},
                }
            )
    for review_task in payload.get("review_tasks") or []:
        timeline.append(
            {
                "timestamp": review_task["requested_at"],
                "kind": "review_task",
                "name": review_task["review_type"],
                "status": review_task["status"],
                "details": {"review_task_id": review_task["review_task_id"], "priority": review_task["priority"]},
            }
        )
    for event in telemetry_events:
        timeline.append(
            {
                "timestamp": event.get("created_at"),
                "kind": "telemetry",
                "name": event.get("event_type"),
                "status": str(((event.get("payload") or {}).get("status")) or "recorded"),
                "details": event.get("payload") or {},
            }
        )
    if payload.get("finished_at"):
        timeline.append(
            {
                "timestamp": payload["finished_at"],
                "kind": "run",
                "name": "run.finished",
                "status": payload["status"],
                "details": {"current_step": payload.get("current_step")},
            }
        )
    timeline.sort(key=lambda item: str(item.get("timestamp") or ""))
    return {"status": "ok", "run_id": run_id, "trace_id": payload.get("trace_id"), "timeline": timeline}


@router.post("/agent-runs/{run_id}/cancel", dependencies=[Depends(require_permissions("agent_run:cancel"))])
def cancel_agent_run(request: Request, run_id: str) -> dict[str, object]:
    manager = RunManager(request.app.state.settings.database_path)
    actor = get_actor_context(request)
    if not manager.cancel_run(run_id):
        raise HTTPException(status_code=409, detail=f"Agent run '{run_id}' cannot be cancelled in its current state.")
    AuditService(request.app.state.settings).record(
        actor=actor,
        action="agent_run.cancel",
        resource_type="agent_run",
        resource_id=run_id,
        run_id=run_id,
        trace_id=(manager.get_run_detail(run_id) or {}).get("trace_id"),
    )
    return {"status": "ok", "run_id": run_id}


@router.post("/agent-runs/{run_id}/resume", dependencies=[Depends(require_permissions("agent_run:resume"))])
def resume_agent_run(request: Request, run_id: str) -> dict[str, object]:
    manager = RunManager(request.app.state.settings.database_path)
    actor = get_actor_context(request)
    if not manager.resume_run(run_id):
        raise HTTPException(status_code=409, detail=f"Agent run '{run_id}' cannot be resumed in its current state.")
    AuditService(request.app.state.settings).record(
        actor=actor,
        action="agent_run.resume",
        resource_type="agent_run",
        resource_id=run_id,
        run_id=run_id,
        trace_id=(manager.get_run_detail(run_id) or {}).get("trace_id"),
    )
    return {"status": "ok", "run_id": run_id}
