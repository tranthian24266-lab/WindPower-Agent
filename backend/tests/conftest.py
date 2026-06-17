from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_test_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    # Keep tests deterministic even when developers have local `.env` values configured.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("WINDPOWER_DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("WINDPOWER_QDRANT_ENABLED", raising=False)
    monkeypatch.delenv("QDRANT_ENABLED", raising=False)
    monkeypatch.delenv("WINDPOWER_QDRANT_URL", raising=False)
    monkeypatch.delenv("QDRANT_URL", raising=False)
