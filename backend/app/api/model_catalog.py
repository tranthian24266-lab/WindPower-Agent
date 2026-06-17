from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.auth import require_write_api_key
from app.core.model_catalog import ModelCatalogService
from app.core.model_router import ModelRouterError, ModelRouterService, ModelSelectionRequest
from app.core.model_sync import ModelSyncError, ModelSyncService
from app.core.model_validation import ModelValidationError, ModelValidationService
from app.db.schemas import ModelAliasUpdateRequest


router = APIRouter(prefix="/model-catalog", tags=["model-catalog"])
SYSTEM_ALIASES = {"default", "champion", "canary", "fallback"}


@router.get("/models")
def list_catalog_models(
    request: Request,
    q: Optional[str] = Query(default=None),
    task_type: Optional[str] = Query(default=None),
    subtask_type: Optional[str] = Query(default=None),
    component: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    validation_status: Optional[str] = Query(default=None),
    alias: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: Optional[int] = Query(default=None, ge=1),
    sort_by: str = Query(default="family_code"),
    sort_order: str = Query(default="asc"),
) -> dict[str, object]:
    settings = request.app.state.settings
    resolved_page_size = min(
        page_size or settings.model_catalog_page_size_default,
        settings.model_catalog_page_size_max,
    )
    service = ModelCatalogService(settings.database_path)
    payload = service.list_catalog_models(
        q=q,
        task_type=task_type,
        subtask_type=subtask_type,
        component=component,
        status=status,
        validation_status=validation_status,
        alias=alias,
        page=page,
        page_size=resolved_page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return {"status": "ok", **payload}


@router.get("/models/{family_id}")
def get_catalog_model(request: Request, family_id: str) -> dict[str, object]:
    settings = request.app.state.settings
    service = ModelCatalogService(settings.database_path)
    family = service.get_family_detail(family_id)
    if family is None:
        raise HTTPException(status_code=404, detail=f"Model family does not exist: {family_id}")
    return {"status": "ok", "model": family}


@router.get("/models/{family_id}/versions")
def list_catalog_model_versions(request: Request, family_id: str) -> dict[str, object]:
    settings = request.app.state.settings
    service = ModelCatalogService(settings.database_path)
    family = service.get_family_detail(family_id)
    if family is None:
        raise HTTPException(status_code=404, detail=f"Model family does not exist: {family_id}")
    versions = service.list_family_versions(family_id)
    return {"status": "ok", "family_id": family_id, "count": len(versions), "versions": versions}


@router.get("/model-versions/{model_version_id}")
def get_catalog_model_version(request: Request, model_version_id: str) -> dict[str, object]:
    settings = request.app.state.settings
    service = ModelCatalogService(settings.database_path)
    version = service.get_model_version_detail(model_version_id)
    if version is None:
        raise HTTPException(status_code=404, detail=f"Model version does not exist: {model_version_id}")
    return {"status": "ok", "model_version": version}


@router.post("/sync", dependencies=[Depends(require_write_api_key)])
def sync_model_catalog(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    service = ModelSyncService(
        settings.database_path,
        settings.resolved_littlemodel_root,
        default_alias=settings.model_catalog_default_alias,
    )
    try:
        result = service.sync_registry()
    except ModelSyncError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "status": result.status,
        "sync_run_id": result.sync_run_id,
        "source_path": result.source_path,
        "discovered_count": result.discovered_count,
        "upserted_count": result.upserted_count,
        "failed_count": result.failed_count,
        "details": result.details,
        "started_at": result.started_at,
        "finished_at": result.finished_at,
        "summary": f"Synchronized {result.upserted_count} models from the legacy registry.",
    }


@router.post("/model-versions/{model_version_id}/validate", dependencies=[Depends(require_write_api_key)])
def validate_model_catalog_version(request: Request, model_version_id: str) -> dict[str, object]:
    settings = request.app.state.settings
    service = ModelValidationService(settings.database_path, settings.resolved_littlemodel_root)
    try:
        result = service.validate_catalog_version(model_version_id)
    except ModelValidationError as exc:
        message = str(exc)
        status_code = 404 if message.startswith("Model version does not exist") else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
    return {
        "validation_run_id": result.validation_run_id,
        "status": result.status,
        "summary": result.summary,
        "details": result.details,
    }


@router.put("/models/{family_id}/aliases/{alias_name}", dependencies=[Depends(require_write_api_key)])
def assign_model_alias(
    request: Request,
    family_id: str,
    alias_name: str,
    payload: ModelAliasUpdateRequest,
) -> dict[str, object]:
    if alias_name not in SYSTEM_ALIASES:
        raise HTTPException(status_code=400, detail=f"Unsupported alias name: {alias_name}")

    settings = request.app.state.settings
    service = ModelCatalogService(settings.database_path)
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        with service.database.connect() as connection:
            service.assign_alias(
                connection,
                family_id=family_id,
                alias_name=alias_name,
                model_version_id=payload.model_version_id,
                created_at=timestamp,
                updated_at=timestamp,
            )
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "does not exist" in message else 400
        raise HTTPException(status_code=status_code, detail=message) from exc

    family = service.get_family_detail(family_id)
    return {
        "status": "ok",
        "family_id": family_id,
        "alias_name": alias_name,
        "model_version_id": payload.model_version_id,
        "reason": payload.reason,
        "aliases": family["aliases"] if family is not None else [],
    }


@router.get("/routing/preview")
def preview_model_routing(
    request: Request,
    task_type: str = Query(..., min_length=1),
    subtask_type: Optional[str] = Query(default=None),
    component: Optional[str] = Query(default=None),
    input_format: Optional[str] = Query(default=None),
    preferred_alias: Optional[str] = Query(default=None),
    preferred_model_id: Optional[str] = Query(default=None),
) -> dict[str, object]:
    settings = request.app.state.settings
    router_service = ModelRouterService(
        settings.database_path,
        settings.resolved_littlemodel_root,
        catalog_enabled=settings.model_catalog_enabled,
        fallback_to_v1=settings.model_router_fallback_to_v1,
        default_alias=settings.model_catalog_default_alias,
    )
    catalog = ModelCatalogService(settings.database_path)
    try:
        selection = router_service.select_model(
            ModelSelectionRequest(
                task_type=task_type,
                subtask_type=subtask_type,
                component=component,
                input_format=input_format,
                preferred_alias=preferred_alias,
                preferred_model_id=preferred_model_id,
            )
        )
    except ModelRouterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "ok",
        "selected_model_version_id": selection.model_version_id,
        "selected_legacy_model_id": selection.legacy_model_id,
        "selection_reason": selection.selection_reason,
        "model_alias": selection.model_alias,
        "evaluated_candidates": catalog.list_candidates_for_task(task_type),
    }
