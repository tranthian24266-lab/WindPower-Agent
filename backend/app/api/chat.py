from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.core.agents.orchestrator_agent import OrchestratorAgent
from app.core.agent_runtime.run_manager import RunManager
from app.core.agent_runtime.step_executor import StepExecutor
from app.core.agent_runtime.tool_registry import ToolRegistry
from app.core.agent_service import AgentService, AgentServiceError
from app.core.audit_service import AuditService
from app.core.auth import get_actor_context
from app.core.telemetry_service import TelemetryService
from app.db.schemas import ChatRequest


router = APIRouter(tags=["chat"])


@router.post("/chat")
def chat(request: Request, payload: ChatRequest) -> dict[str, object]:
    settings = request.app.state.settings
    actor = get_actor_context(request)
    orchestrator = OrchestratorAgent(settings)
    run_manager = RunManager(settings.database_path)
    run_id = run_manager.create_run(
        run_type="chat_answer",
        case_id=payload.case_id,
        session_id=payload.session_id,
        input_payload=payload.model_dump(),
        triggered_by=actor.actor_id,
    )
    AuditService(settings).record(
        actor=actor,
        action="agent_run.create",
        resource_type="agent_run",
        resource_id=run_id,
        run_id=run_id,
        trace_id=(run_manager.get_run_detail(run_id) or {}).get("trace_id"),
        details={"run_type": "chat_answer", "case_id": payload.case_id},
    )
    tool_registry = ToolRegistry()
    tool_registry.register(
        "chat.answer",
        lambda: orchestrator.run_chat_answer(
            run_id=run_id,
            case_id=payload.case_id,
            question=payload.question,
            session_id=payload.session_id,
            actor=actor,
        ),
        allowed_run_types=("chat_answer",),
    )
    executor = StepExecutor(run_manager, tool_registry, TelemetryService(settings))
    try:
        result = executor.execute_tool(
            run_id=run_id,
            step_name="chat.answer",
            tool_name="chat.answer",
            request_payload=payload.model_dump(),
        )
        run_manager.complete_run(run_id, output_payload=result, current_step="chat.answer")
        return result
    except AgentServiceError as exc:
        run_manager.fail_run(
            run_id,
            error_payload={"type": exc.__class__.__name__, "message": str(exc)},
            current_step="chat.answer",
        )
        message = str(exc)
        if message.startswith("Diagnosis case does not exist"):
            status_code = 404
        elif message.startswith("DeepSeek API request failed"):
            status_code = 502
        else:
            status_code = 500
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except Exception as exc:
        run_manager.fail_run(
            run_id,
            error_payload={"type": exc.__class__.__name__, "message": str(exc)},
            current_step="chat.answer",
        )
        raise


@router.get("/chat/history/{case_id}")
def chat_history(request: Request, case_id: str) -> dict[str, object]:
    settings = request.app.state.settings
    service = AgentService(settings)
    try:
        return service.get_history(case_id)
    except AgentServiceError as exc:
        status_code = 404 if str(exc).startswith("Diagnosis case does not exist") else 500
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
