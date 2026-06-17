from __future__ import annotations

from typing import Any, Callable

from app.core.agents.orchestrator_agent import OrchestratorAgent
from app.core.agent_runtime.run_manager import RunManager
from app.core.agent_runtime.step_executor import StepExecutor
from app.core.agent_runtime.tool_registry import ToolRegistry
from app.core.settings import Settings
from app.core.telemetry_service import TelemetryService


def execute_job(settings: Settings, run_manager: RunManager, job_type: str, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    handlers: dict[str, Callable[[Settings, RunManager, str, dict[str, Any]], dict[str, Any]]] = {
        "chat_answer": execute_chat_answer_job,
        "enhanced_report": execute_enhanced_report_job,
    }
    handler = handlers.get(job_type)
    if handler is None:
        raise RuntimeError(f"Unsupported job type: {job_type}")
    return handler(settings, run_manager, run_id, payload)


def execute_chat_answer_job(
    settings: Settings,
    run_manager: RunManager,
    run_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    case_id = str(payload["case_id"])
    question = str(payload["question"])
    session_id = payload.get("session_id")
    orchestrator = OrchestratorAgent(settings)
    tool_registry = ToolRegistry()
    tool_registry.register(
        "chat.answer",
        lambda: orchestrator.run_chat_answer(run_id=run_id, case_id=case_id, question=question, session_id=session_id),
        allowed_run_types=("chat_answer",),
    )
    executor = StepExecutor(run_manager, tool_registry, TelemetryService(settings))
    result = executor.execute_tool(
        run_id=run_id,
        step_name="chat.answer",
        tool_name="chat.answer",
        request_payload=payload,
    )
    run_manager.complete_run(run_id, output_payload=result, current_step="chat.answer")
    return result


def execute_enhanced_report_job(
    settings: Settings,
    run_manager: RunManager,
    run_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    case_id = str(payload["case_id"])
    orchestrator = OrchestratorAgent(settings)
    tool_registry = ToolRegistry()
    tool_registry.register(
        "enhanced_report.generate",
        lambda: orchestrator.run_enhanced_report(run_id=run_id, case_id=case_id),
        allowed_run_types=("enhanced_report",),
    )
    executor = StepExecutor(run_manager, tool_registry, TelemetryService(settings))
    result = executor.execute_tool(
        run_id=run_id,
        step_name="enhanced_report.generate",
        tool_name="enhanced_report.generate",
        request_payload=payload,
    )
    return result
