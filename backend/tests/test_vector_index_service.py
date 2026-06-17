from __future__ import annotations

import builtins
from pathlib import Path

from app.core.settings import Settings
from app.core.vector_index_service import VectorIndexService


def test_vector_index_service_uses_rest_fallback_when_sdk_unavailable(tmp_path: Path, monkeypatch) -> None:
    settings = Settings(
        backend_root=tmp_path,
        littlemodel_root=tmp_path / "littlemodel",
        qdrant_enabled=True,
        qdrant_url="http://127.0.0.1:6333",
        _env_file=None,
    )
    service = VectorIndexService(settings)

    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):  # type: ignore[override]
        if name == "qdrant_client":
            raise ImportError("sdk unavailable")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    client = service._create_client()

    assert client is not None
    assert client.__class__.__name__ == "_RestQdrantClient"
