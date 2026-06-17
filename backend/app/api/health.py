from __future__ import annotations

from fastapi import APIRouter, Request


router = APIRouter(tags=["health"])


@router.get("/health")
def get_health(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    littlemodel_root = settings.resolved_littlemodel_root
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "littlemodel_root": str(littlemodel_root),
        "littlemodel_available": littlemodel_root.exists(),
    }
