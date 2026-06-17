from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.core.agent_runtime.guardrails import AgentGuardrails

ToolHandler = Callable[[], dict[str, Any]]


@dataclass
class RegisteredTool:
    handler: ToolHandler
    allowed_run_types: tuple[str, ...]


class ToolRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, RegisteredTool] = {}
        self._guardrails = AgentGuardrails()

    def register(self, tool_name: str, handler: ToolHandler, *, allowed_run_types: tuple[str, ...] | None = None) -> None:
        self._handlers[tool_name] = RegisteredTool(
            handler=handler,
            allowed_run_types=tuple(allowed_run_types or ()),
        )

    def invoke(self, tool_name: str, *, run_type: str | None = None) -> dict[str, Any]:
        registered = self._handlers.get(tool_name)
        if registered is None:
            raise KeyError(f"Tool '{tool_name}' is not registered.")
        self._guardrails.validate_tool_access(
            tool_name=tool_name,
            run_type=run_type,
            allowed_run_types=registered.allowed_run_types,
        )
        return registered.handler()
