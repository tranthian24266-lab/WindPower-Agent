from __future__ import annotations

from dataclasses import dataclass
import json
from time import perf_counter
from typing import Any

import httpx

from app.core.settings import Settings
from app.core.telemetry_service import TelemetryService


class DeepSeekClientError(RuntimeError):
    """Raised when the DeepSeek API cannot satisfy a request safely."""

    def __init__(self, message: str, *, code: str = "unknown_error"):
        super().__init__(message)
        self.code = code


@dataclass
class DeepSeekChatResult:
    content: str
    reasoning_content: str | None
    raw_payload: dict[str, Any]
    usage: dict[str, Any] | None


class DeepSeekClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.telemetry = TelemetryService(settings)

    def create_chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int,
        thinking_enabled: bool,
        reasoning_effort: str,
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.2,
        telemetry_context: dict[str, Any] | None = None,
    ) -> DeepSeekChatResult:
        if not self.settings.deepseek_api_key:
            raise DeepSeekClientError("DeepSeek API key is not configured.", code="missing_api_key")

        started = perf_counter()
        request_mode = "json_completion" if response_format == {"type": "json_object"} else "chat_completion"
        payload: dict[str, Any] = {
            "model": self.settings.deepseek_model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "thinking": {"type": "enabled" if thinking_enabled else "disabled"},
        }
        if thinking_enabled:
            payload["reasoning_effort"] = reasoning_effort
        if response_format is not None:
            payload["response_format"] = response_format

        base_url = self.settings.deepseek_base_url.rstrip("/")
        try:
            response = httpx.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.deepseek_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.settings.deepseek_timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip()
            self._record_call(
                request_mode=request_mode,
                success=False,
                duration_ms=self._elapsed_ms(started),
                max_tokens=max_tokens,
                thinking_enabled=thinking_enabled,
                reasoning_effort=reasoning_effort,
                usage=None,
                error=detail or str(exc),
                message_count=len(messages),
                telemetry_context=telemetry_context,
            )
            raise DeepSeekClientError(
                f"DeepSeek API request failed: {detail or exc}",
                code="http_status_error",
            ) from exc
        except httpx.HTTPError as exc:
            self._record_call(
                request_mode=request_mode,
                success=False,
                duration_ms=self._elapsed_ms(started),
                max_tokens=max_tokens,
                thinking_enabled=thinking_enabled,
                reasoning_effort=reasoning_effort,
                usage=None,
                error=str(exc),
                message_count=len(messages),
                telemetry_context=telemetry_context,
            )
            raise DeepSeekClientError(
                f"DeepSeek API request failed: {exc}",
                code="transport_error",
            ) from exc

        raw_payload = response.json()
        choice = self._extract_first_choice(raw_payload)
        message = choice.get("message") or {}
        content = self._extract_message_content(message)
        if not content:
            self._record_call(
                request_mode=request_mode,
                success=False,
                duration_ms=self._elapsed_ms(started),
                max_tokens=max_tokens,
                thinking_enabled=thinking_enabled,
                reasoning_effort=reasoning_effort,
                usage=raw_payload.get("usage") if isinstance(raw_payload.get("usage"), dict) else None,
                error="empty_content",
                message_count=len(messages),
                telemetry_context=telemetry_context,
            )
            raise DeepSeekClientError("DeepSeek API returned empty content.", code="empty_content")
        reasoning_content = message.get("reasoning_content")
        result = DeepSeekChatResult(
            content=content,
            reasoning_content=reasoning_content.strip() if isinstance(reasoning_content, str) and reasoning_content.strip() else None,
            raw_payload=raw_payload,
            usage=raw_payload.get("usage") if isinstance(raw_payload.get("usage"), dict) else None,
        )
        self._record_call(
            request_mode=request_mode,
            success=True,
            duration_ms=self._elapsed_ms(started),
            max_tokens=max_tokens,
            thinking_enabled=thinking_enabled,
            reasoning_effort=reasoning_effort,
            usage=result.usage,
            error=None,
            message_count=len(messages),
            telemetry_context=telemetry_context,
        )
        return result

    def create_json_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int,
        thinking_enabled: bool,
        reasoning_effort: str,
        retry_count: int,
        temperature: float = 0.1,
    ) -> tuple[dict[str, Any], DeepSeekChatResult]:
        attempts = max(1, retry_count + 1)
        last_error: Exception | None = None
        for _ in range(attempts):
            result = self.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                thinking_enabled=thinking_enabled,
                reasoning_effort=reasoning_effort,
                response_format={"type": "json_object"},
                temperature=temperature,
            )
            try:
                return self.parse_json_content(result.content), result
            except Exception as exc:  # pragma: no cover - exercised via retry behavior
                last_error = exc
        raise DeepSeekClientError(
            f"DeepSeek JSON output parsing failed: {last_error}",
            code=getattr(last_error, "code", "json_parse_error"),
        )

    def _record_call(
        self,
        *,
        request_mode: str,
        success: bool,
        duration_ms: int,
        max_tokens: int,
        thinking_enabled: bool,
        reasoning_effort: str,
        usage: dict[str, Any] | None,
        error: str | None,
        message_count: int,
        telemetry_context: dict[str, Any] | None,
    ) -> None:
        payload = {
            "model_name": self.settings.deepseek_model_name,
            "request_mode": request_mode,
            "success": success,
            "duration_ms": duration_ms,
            "max_tokens": max_tokens,
            "thinking_enabled": thinking_enabled,
            "reasoning_effort": reasoning_effort,
            "message_count": message_count,
            "usage": usage or {},
            "error": error,
        }
        if telemetry_context:
            payload.update(telemetry_context)
        self.telemetry.record(
            "deepseek_call",
            payload,
        )

    def _elapsed_ms(self, started: float) -> int:
        return int((perf_counter() - started) * 1000)

    def _extract_first_choice(self, payload: dict[str, Any]) -> dict[str, Any]:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise DeepSeekClientError("DeepSeek API returned no choices.", code="no_choices")
        first = choices[0]
        if not isinstance(first, dict):
            raise DeepSeekClientError(
                "DeepSeek API returned an invalid choice payload.",
                code="invalid_choice",
            )
        return first

    def _extract_message_content(self, message: dict[str, Any]) -> str:
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            return "\n".join(
                part.get("text", "").strip()
                for part in content
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            ).strip()
        return ""

    def parse_json_content(self, content: str) -> dict[str, Any]:
        normalized = content.strip()
        if normalized.startswith("```"):
            normalized = normalized.strip("`")
            if normalized.startswith("json"):
                normalized = normalized[4:]
            normalized = normalized.strip()
        try:
            parsed = json.loads(normalized)
        except json.JSONDecodeError as exc:
            raise DeepSeekClientError(f"DeepSeek JSON output parsing failed: {exc}", code="json_parse_error") from exc
        if not isinstance(parsed, dict):
            raise DeepSeekClientError(
                "DeepSeek JSON output must be a JSON object.",
                code="invalid_json_object",
            )
        return parsed
