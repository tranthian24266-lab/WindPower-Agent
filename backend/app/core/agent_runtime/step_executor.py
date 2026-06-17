from __future__ import annotations

from time import perf_counter
from typing import Any

from app.core.agent_runtime.run_manager import RunManager
from app.core.agent_runtime.tool_registry import ToolRegistry
from app.core.telemetry_service import TelemetryService


class StepExecutor:
    def __init__(
        self,
        run_manager: RunManager,
        tool_registry: ToolRegistry,
        telemetry: TelemetryService | None = None,
    ):
        self.run_manager = run_manager
        self.tool_registry = tool_registry
        self.telemetry = telemetry

    def execute_tool(
        self,
        *,
        run_id: str,
        step_name: str,
        tool_name: str,
        request_payload: dict[str, Any] | None = None,
        tool_version: str | None = None,
    ) -> dict[str, Any]:
        run_detail = self.run_manager.get_run_detail(run_id)
        run_type = str((run_detail or {}).get("run_type") or "")
        trace_id = str((run_detail or {}).get("trace_id") or "")
        step_span_id = self.telemetry.new_span_id() if self.telemetry and trace_id else None
        tool_span_id = self.telemetry.new_span_id() if self.telemetry and trace_id else None
        self.run_manager.mark_running(run_id, current_step=step_name)
        step_id = self.run_manager.start_step(
            run_id=run_id,
            step_name=step_name,
            step_type="tool_call",
            input_payload=request_payload,
        )
        tool_call_id = self.run_manager.start_tool_call(
            run_id=run_id,
            step_id=step_id,
            tool_name=tool_name,
            request_payload=request_payload,
            tool_version=tool_version,
        )
        started = perf_counter()
        try:
            result = self.tool_registry.invoke(tool_name, run_type=run_type)
        except Exception as exc:
            duration_ms = int((perf_counter() - started) * 1000)
            error_payload = {
                "type": exc.__class__.__name__,
                "message": str(exc),
            }
            self.run_manager.fail_tool_call(
                tool_call_id,
                error_payload=error_payload,
                duration_ms=duration_ms,
            )
            self.run_manager.fail_step(
                step_id,
                error_payload=error_payload,
                duration_ms=duration_ms,
            )
            if self.telemetry and trace_id and step_span_id and tool_span_id:
                attributes = {"run_id": run_id, "step_id": step_id, "tool_call_id": tool_call_id, "tool_name": tool_name}
                self.telemetry.record_trace_span(
                    trace_id=trace_id,
                    span_id=tool_span_id,
                    parent_span_id=step_span_id,
                    name=f"tool:{tool_name}",
                    status="failed",
                    attributes={**attributes, "duration_ms": duration_ms, "error": error_payload},
                )
                self.telemetry.record_trace_span(
                    trace_id=trace_id,
                    span_id=step_span_id,
                    parent_span_id=None,
                    name=f"step:{step_name}",
                    status="failed",
                    attributes={**attributes, "duration_ms": duration_ms, "error": error_payload},
                )
            raise

        duration_ms = int((perf_counter() - started) * 1000)
        self.run_manager.complete_tool_call(
            tool_call_id,
            response_payload=result,
            duration_ms=duration_ms,
        )
        self.run_manager.complete_step(
            step_id,
            output_payload=result,
            duration_ms=duration_ms,
        )
        if self.telemetry and trace_id and step_span_id and tool_span_id:
            attributes = {"run_id": run_id, "step_id": step_id, "tool_call_id": tool_call_id, "tool_name": tool_name}
            self.telemetry.record_trace_span(
                trace_id=trace_id,
                span_id=tool_span_id,
                parent_span_id=step_span_id,
                name=f"tool:{tool_name}",
                status="succeeded",
                attributes={**attributes, "duration_ms": duration_ms},
            )
            self.telemetry.record_trace_span(
                trace_id=trace_id,
                span_id=step_span_id,
                parent_span_id=None,
                name=f"step:{step_name}",
                status="succeeded",
                attributes={**attributes, "duration_ms": duration_ms},
            )
        return result
