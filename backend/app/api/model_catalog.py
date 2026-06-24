from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field

from app.core.audit_service import AuditService
from app.core.auth import ActorContext, require_permissions, require_write_api_key
from app.core.model_catalog import ModelCatalogService
from app.core.model_package_service import ModelPackageError, ModelPackageService
from app.core.model_router import ModelRouterError, ModelRouterService, ModelSelectionRequest
from app.core.model_sync import ModelSyncError, ModelSyncService
from app.core.model_validation import ModelValidationError, ModelValidationService
from app.db.schemas import ModelAliasUpdateRequest


router = APIRouter(prefix="/model-catalog", tags=["model-catalog"])
SYSTEM_ALIASES = {"default", "champion", "canary", "fallback"}


class ModelPackageMetadataUpdate(BaseModel):
    model_name: Optional[str] = Field(default=None, max_length=160)
    description: Optional[str] = Field(default=None, max_length=2000)
    dataset: Optional[str] = Field(default=None, max_length=500)
    limitations: Optional[list[str]] = None


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


@router.post("/packages/upload")
async def upload_model_package(
    request: Request,
    file: UploadFile = File(...),
    actor: ActorContext = Depends(require_permissions("model_catalog:manage")),
) -> dict[str, object]:
    settings = request.app.state.settings
    content = await file.read(settings.model_package_max_upload_bytes + 1)
    try:
        package = ModelPackageService(settings).create_upload(file.filename or "model.zip", content)
    except ModelPackageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    AuditService(settings).record(
        actor=actor,
        action="model_package.upload",
        resource_type="model_package",
        resource_id=str(package["upload_id"]),
        details={"filename": package["filename"], "sha256": package["sha256"]},
    )
    return {"status": "ok", "package": package}


@router.get("/packages/{upload_id}")
def get_model_package(request: Request, upload_id: str) -> dict[str, object]:
    try:
        package = ModelPackageService(request.app.state.settings).get_upload(upload_id)
    except ModelPackageError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "ok", "package": package}


@router.put("/packages/{upload_id}/metadata")
def update_model_package_metadata(
    request: Request,
    upload_id: str,
    payload: ModelPackageMetadataUpdate,
    actor: ActorContext = Depends(require_permissions("model_catalog:manage")),
) -> dict[str, object]:
    try:
        package = ModelPackageService(request.app.state.settings).update_metadata(
            upload_id,
            payload.model_dump(exclude_unset=True),
        )
    except ModelPackageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    AuditService(request.app.state.settings).record(
        actor=actor,
        action="model_package.metadata_update",
        resource_type="model_package",
        resource_id=upload_id,
    )
    return {"status": "ok", "package": package}


@router.post("/packages/{upload_id}/validate")
def validate_model_package(
    request: Request,
    upload_id: str,
    actor: ActorContext = Depends(require_permissions("model_catalog:manage")),
) -> dict[str, object]:
    try:
        package = ModelPackageService(request.app.state.settings).validate_upload(upload_id)
    except ModelPackageError as exc:
        AuditService(request.app.state.settings).record(
            actor=actor,
            action="model_package.validate",
            resource_type="model_package",
            resource_id=upload_id,
            outcome="failed",
            details={"error": str(exc)},
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    AuditService(request.app.state.settings).record(
        actor=actor,
        action="model_package.validate",
        resource_type="model_package",
        resource_id=upload_id,
    )
    return {"status": "ok", "package": package}


@router.post("/packages/{upload_id}/publish")
def publish_model_package(
    request: Request,
    upload_id: str,
    actor: ActorContext = Depends(require_permissions("model_catalog:manage")),
) -> dict[str, object]:
    try:
        package = ModelPackageService(request.app.state.settings).publish_upload(upload_id)
    except ModelPackageError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    AuditService(request.app.state.settings).record(
        actor=actor,
        action="model_package.publish",
        resource_type="model_version",
        resource_id=str(package["published_model_version_id"]),
        details={"upload_id": upload_id, "model_dir": package["published_model_dir"]},
    )
    return {"status": "ok", "package": package}


@router.delete("/packages/{upload_id}")
def discard_model_package(
    request: Request,
    upload_id: str,
    actor: ActorContext = Depends(require_permissions("model_catalog:manage")),
) -> dict[str, object]:
    try:
        ModelPackageService(request.app.state.settings).discard_upload(upload_id)
    except ModelPackageError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    AuditService(request.app.state.settings).record(
        actor=actor,
        action="model_package.discard",
        resource_type="model_package",
        resource_id=upload_id,
    )
    return {"status": "deleted", "upload_id": upload_id}


@router.post("/model-versions/{model_version_id}/archive")
def archive_model_catalog_version(
    request: Request,
    model_version_id: str,
    actor: ActorContext = Depends(require_permissions("model_catalog:manage")),
) -> dict[str, object]:
    try:
        version = ModelPackageService(request.app.state.settings).archive_version(model_version_id)
    except ModelPackageError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    AuditService(request.app.state.settings).record(
        actor=actor,
        action="model_version.archive",
        resource_type="model_version",
        resource_id=model_version_id,
    )
    return {"status": "ok", "model_version": version}


@router.delete("/model-versions/{model_version_id}")
def delete_model_catalog_version(
    request: Request,
    model_version_id: str,
    actor: ActorContext = Depends(require_permissions("model_catalog:manage")),
) -> dict[str, object]:
    try:
        result = ModelPackageService(request.app.state.settings).delete_version(model_version_id)
    except ModelPackageError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    AuditService(request.app.state.settings).record(
        actor=actor,
        action="model_version.delete",
        resource_type="model_version",
        resource_id=model_version_id,
        details={"trash_path": result["trash_path"]},
    )
    return result


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
    version = service.get_model_version_detail(payload.model_version_id)
    if version is None:
        raise HTTPException(status_code=404, detail=f"Model version does not exist: {payload.model_version_id}")
    if version["validation_status"] != "passed" or version["status"] == "archived":
        raise HTTPException(status_code=409, detail="Only validated, non-archived model versions can receive aliases.")
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
