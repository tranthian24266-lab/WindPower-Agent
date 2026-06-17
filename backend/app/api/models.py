from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.core.model_registry import ModelRegistryError, ModelRegistryService


router = APIRouter(tags=["models"])


@router.get("/models")
def list_models(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    service = ModelRegistryService(settings.resolved_littlemodel_root)
    try:
        models = service.list_models()
    except ModelRegistryError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"status": "ok", "count": len(models), "models": models}
