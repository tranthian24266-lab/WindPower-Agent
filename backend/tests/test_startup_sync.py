from __future__ import annotations

from pathlib import Path

import pytest

from app.core.model_catalog import ModelCatalogService
from app.core.model_sync import ModelSyncError, ModelSyncService
from app.core.settings import Settings
from app.main import create_app


LITTLEMODEL_ROOT = Path(r"C:\Users\luzian\Desktop\littlemodel")


def test_create_app_syncs_model_catalog_by_default(tmp_path: Path) -> None:
    settings = Settings(backend_root=tmp_path, littlemodel_root=LITTLEMODEL_ROOT)

    app = create_app(settings)

    catalog = ModelCatalogService(settings.database_path)
    assert app.state.settings.model_catalog_enabled is True
    assert len(catalog.list_versions()) == 3
    assert len(catalog.list_aliases()) == 3


def test_create_app_skips_sync_when_disabled(tmp_path: Path) -> None:
    settings = Settings(
        backend_root=tmp_path,
        littlemodel_root=LITTLEMODEL_ROOT,
        model_catalog_enabled=False,
        model_sync_on_startup=False,
    )

    create_app(settings)

    catalog = ModelCatalogService(settings.database_path)
    assert catalog.list_versions() == []


def test_create_app_continues_when_sync_fails_but_fallback_enabled(tmp_path: Path, monkeypatch) -> None:
    def raise_sync_error(self) -> None:
        raise ModelSyncError("forced sync failure")

    monkeypatch.setattr(ModelSyncService, "sync_registry", raise_sync_error)

    settings = Settings(
        backend_root=tmp_path,
        littlemodel_root=LITTLEMODEL_ROOT,
        model_catalog_enabled=True,
        model_sync_on_startup=True,
        model_router_fallback_to_v1=True,
    )

    app = create_app(settings)

    catalog = ModelCatalogService(settings.database_path)
    assert app.state.settings.model_router_fallback_to_v1 is True
    assert catalog.list_versions() == []


def test_create_app_raises_when_sync_fails_without_fallback(tmp_path: Path, monkeypatch) -> None:
    def raise_sync_error(self) -> None:
        raise ModelSyncError("forced sync failure")

    monkeypatch.setattr(ModelSyncService, "sync_registry", raise_sync_error)

    settings = Settings(
        backend_root=tmp_path,
        littlemodel_root=LITTLEMODEL_ROOT,
        model_catalog_enabled=True,
        model_sync_on_startup=True,
        model_router_fallback_to_v1=False,
    )

    with pytest.raises(Exception):
        create_app(settings)


def test_settings_parse_cors_origins_from_json_string() -> None:
    settings = Settings(cors_origins='["http://127.0.0.1:5173", "http://localhost:5173"]')

    assert settings.cors_origins == ["http://127.0.0.1:5173", "http://localhost:5173"]
