from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.deepseek_client import DeepSeekChatResult
from app.core.settings import Settings
from app.main import create_app


LITTLEMODEL_ROOT = Path(r"C:\Users\luzian\Desktop\littlemodel")


def _create_client(tmp_path: Path, **overrides: object) -> TestClient:
    payload: dict[str, object] = {
        "backend_root": tmp_path,
        "littlemodel_root": LITTLEMODEL_ROOT,
        "agent_mode": "local",
        "deepseek_api_key": None,
    }
    payload.update(overrides)
    settings = Settings(**payload)
    return TestClient(create_app(settings))


def _create_case(client: TestClient, task_type: str, path: Path) -> str:
    with path.open("rb") as handle:
        upload = client.post("/api/upload", files={"file": (path.name, handle)})
    file_id = upload.json()["file"]["file_id"]
    diagnose = client.post("/api/diagnose", json={"file_id": file_id, "task_type": task_type})
    return diagnose.json()["case_id"]


def test_chat_answers_for_each_case_type(tmp_path: Path) -> None:
    client = _create_client(tmp_path)
    cases = [
        ("fault_diagnosis", LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy", "prediction"),
        ("rul_prediction", LITTLEMODEL_ROOT / "rul_prediction" / "test_data" / "split_60_40" / "data-20130406T221209Z.mat", "RUL"),
        ("anomaly_detection", LITTLEMODEL_ROOT / "anomaly_detection" / "test_data" / "test_data_sample.csv", "anomaly_ratio"),
    ]

    for task_type, path, needle in cases:
        case_id = _create_case(client, task_type, path)
        response = client.post("/api/chat", json={"case_id": case_id, "question": "请解释这次结果"})
        assert response.status_code == 200
        assert response.json()["mode"] == "rule_based_local"
        assert needle in response.json()["answer"]


def test_chat_history_persists_messages(tmp_path: Path) -> None:
    client = _create_client(tmp_path)
    case_id = _create_case(client, "fault_diagnosis", LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy")
    reply = client.post("/api/chat", json={"case_id": case_id, "question": "请解释风险"})
    session_id = reply.json()["session_id"]
    assert session_id
    assert reply.json()["mode"] == "rule_based_local"

    history = client.get(f"/api/chat/history/{case_id}")
    assert history.status_code == 200
    messages = history.json()["messages"]
    assert len(messages) >= 2
    assert {message["role"] for message in messages} >= {"user", "assistant"}


def test_chat_uses_deepseek_client_with_configurable_reasoning(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeDeepSeekClient:
        def __init__(self, settings: Settings):
            captured["settings"] = settings

        def create_chat_completion(
            self,
            *,
            messages: list[dict[str, object]],
            max_tokens: int,
            thinking_enabled: bool,
            reasoning_effort: str,
            response_format: dict[str, object] | None = None,
            temperature: float = 0.2,
        ) -> DeepSeekChatResult:
            captured["messages"] = messages
            captured["max_tokens"] = max_tokens
            captured["thinking_enabled"] = thinking_enabled
            captured["reasoning_effort"] = reasoning_effort
            captured["response_format"] = response_format
            captured["temperature"] = temperature
            return DeepSeekChatResult(
                content="这是 DeepSeek 回答。",
                reasoning_content="先分析再回答。",
                raw_payload={"usage": {"total_tokens": 42}},
                usage={"total_tokens": 42},
            )

    monkeypatch.setattr("app.core.agent_service.DeepSeekClient", FakeDeepSeekClient)

    client = _create_client(
        tmp_path,
        agent_mode="auto",
        deepseek_api_key="test-key",
        deepseek_thinking_enabled=False,
        deepseek_reasoning_effort="max",
        deepseek_max_tokens_chat=666,
    )
    case_id = _create_case(client, "fault_diagnosis", LITTLEMODEL_ROOT / "fault_diagnosis" / "test_data" / "test_sensor1_x.npy")

    response = client.post("/api/chat", json={"case_id": case_id, "question": "请解释这次结果"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "deepseek_api"
    assert payload["answer"].startswith("这是 DeepSeek 回答。")
    assert "高风险案例当前未绑定外部证据引用" in payload["answer"]
    assert captured["thinking_enabled"] is False
    assert captured["reasoning_effort"] == "max"
    assert captured["max_tokens"] == 666

    history = client.get(f"/api/chat/history/{case_id}")
    assistant_messages = [item for item in history.json()["messages"] if item["role"] == "assistant"]
    assert assistant_messages[-1]["message_metadata"]["reasoning_content"] == "先分析再回答。"
