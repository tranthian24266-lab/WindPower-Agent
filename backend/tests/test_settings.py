from __future__ import annotations

from pathlib import Path

import pytest

from app.main import create_app
from app.core.settings import Settings


def test_settings_accept_legacy_and_prefixed_env_names(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "legacy-key")
    monkeypatch.setenv("QDRANT_URL", "http://legacy-qdrant:6333")

    legacy = Settings(_env_file=None)

    assert legacy.deepseek_api_key == "legacy-key"
    assert legacy.qdrant_url == "http://legacy-qdrant:6333"

    monkeypatch.setenv("WINDPOWER_DEEPSEEK_API_KEY", "prefixed-key")
    monkeypatch.setenv("WINDPOWER_QDRANT_URL", "http://prefixed-qdrant:6333")

    prefixed = Settings(_env_file=None)

    assert prefixed.deepseek_api_key == "prefixed-key"
    assert prefixed.qdrant_url == "http://prefixed-qdrant:6333"


def test_settings_resolve_littlemodel_root_prefers_explicit_env(monkeypatch, tmp_path: Path) -> None:
    explicit_root = tmp_path / "configured-littlemodel"
    explicit_root.mkdir()
    auto_root = tmp_path / "littlemodel"
    auto_root.mkdir()
    backend_root = tmp_path / "backend"
    backend_root.mkdir()

    monkeypatch.setenv("WINDPOWER_LITTLEMODEL_ROOT", str(explicit_root))

    settings = Settings(backend_root=backend_root, _env_file=None)

    assert settings.littlemodel_root == explicit_root
    assert settings.resolved_littlemodel_root == explicit_root


def test_settings_resolve_littlemodel_root_auto_discovers_workspace_neighbor(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    backend_root = workspace_root / "backend"
    backend_root.mkdir(parents=True)
    auto_root = tmp_path / "littlemodel"
    auto_root.mkdir()

    settings = Settings(backend_root=backend_root, littlemodel_root=None, _env_file=None)

    assert settings.resolved_littlemodel_root == auto_root


def test_create_app_fails_fast_when_littlemodel_root_is_missing(tmp_path: Path) -> None:
    backend_root = tmp_path / "workspace" / "backend"
    backend_root.mkdir(parents=True)
    settings = Settings(backend_root=backend_root, littlemodel_root=None, _env_file=None)

    with pytest.raises(RuntimeError, match="Unable to locate the littlemodel workspace"):
        create_app(settings)
