from __future__ import annotations

from pathlib import Path

from app.core.deepseek_client import DeepSeekClient
from app.core.settings import Settings


LITTLEMODEL_ROOT = Path(r"C:\Users\luzian\Desktop\littlemodel")


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"answer":"ok"}',
                    }
                }
            ],
            "usage": {"total_tokens": 1},
        }


def _build_settings(tmp_path: Path) -> Settings:
    return Settings(
        backend_root=tmp_path,
        littlemodel_root=LITTLEMODEL_ROOT,
        deepseek_api_key="test-key",
        deepseek_base_url="https://api.deepseek.com",
    )


def test_deepseek_client_omits_reasoning_effort_when_thinking_disabled(
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_post(url: str, *, headers: dict[str, str], json: dict[str, object], timeout: float):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr("app.core.deepseek_client.httpx.post", fake_post)

    client = DeepSeekClient(_build_settings(tmp_path))
    result = client.create_chat_completion(
        messages=[{"role": "user", "content": "hello"}],
        max_tokens=256,
        thinking_enabled=False,
        reasoning_effort="high",
        response_format={"type": "json_object"},
    )

    assert result.content == '{"answer":"ok"}'
    payload = captured["json"]
    assert isinstance(payload, dict)
    assert payload["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in payload


def test_deepseek_client_keeps_reasoning_effort_when_thinking_enabled(
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_post(url: str, *, headers: dict[str, str], json: dict[str, object], timeout: float):
        captured["json"] = json
        return _FakeResponse()

    monkeypatch.setattr("app.core.deepseek_client.httpx.post", fake_post)

    client = DeepSeekClient(_build_settings(tmp_path))
    client.create_chat_completion(
        messages=[{"role": "user", "content": "hello"}],
        max_tokens=256,
        thinking_enabled=True,
        reasoning_effort="high",
    )

    payload = captured["json"]
    assert isinstance(payload, dict)
    assert payload["thinking"] == {"type": "enabled"}
    assert payload["reasoning_effort"] == "high"
