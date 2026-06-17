from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.audit_service import AuditService
from app.core.telemetry_service import TelemetryService
from app.core.vector_index_service import VectorIndexService


router = APIRouter(tags=["system"])


@router.get("/system/config-summary")
def get_config_summary(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    littlemodel_root = settings.resolved_littlemodel_root
    qdrant_status = VectorIndexService(settings).get_status()
    qdrant_runtime_enabled = bool(qdrant_status.get("remote_enabled"))
    qdrant_remote_available = bool(qdrant_status.get("remote_available"))
    database_backend = "postgresql" if settings.database_url and settings.database_url.startswith("postgresql://") else "sqlite"

    return {
        "status": "ok",
        "paths": {
            "backend_root": str(settings.backend_root),
            "project_root": str(settings.project_root),
            "littlemodel_root": str(littlemodel_root),
            "littlemodel_root_exists": littlemodel_root.exists(),
            "knowledge_base_path": str(settings.knowledge_base_path),
            "knowledge_base_path_exists": settings.knowledge_base_path.exists(),
            "uploads_path": str(settings.uploads_path),
            "outputs_path": str(settings.outputs_path),
            "reports_path": str(settings.reports_path),
        },
        "integrations": {
            "database_backend": database_backend,
            "database_url_configured": bool(settings.database_url),
            "deepseek_configured": bool(settings.deepseek_api_key),
            "deepseek_base_url": settings.deepseek_base_url,
            "deepseek_model_name": settings.deepseek_model_name,
            "auth_enabled": settings.auth_enabled,
            "api_key_configured": bool(settings.api_key),
            "rbac_enabled": settings.rbac_enabled,
            "audit_enabled": settings.audit_enabled,
            "qdrant_enabled": qdrant_runtime_enabled,
            "qdrant_config_enabled": settings.qdrant_enabled,
            "qdrant_url_configured": bool(settings.qdrant_url),
            "qdrant_remote_available": qdrant_remote_available,
            "qdrant_remote_ping_ok": bool(qdrant_status.get("remote_ping_ok")),
        },
        "features": {
            "base_report_pdf_enabled": settings.base_report_pdf_enabled,
            "enhanced_reports_enabled": settings.enhanced_reports_enabled,
            "knowledge_rag_enabled": settings.knowledge_rag_enabled,
            "chat_rag_enabled": settings.chat_rag_enabled,
            "knowledge_ingestion_enabled": settings.knowledge_ingestion_enabled,
            "knowledge_case_ingestion_enabled": settings.knowledge_case_ingestion_enabled,
            "qdrant_enabled": qdrant_runtime_enabled,
            "qdrant_config_enabled": settings.qdrant_enabled,
        },
    }


@router.get("/system/observability-summary")
def get_observability_summary(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    telemetry = TelemetryService(settings)
    events = telemetry.list_events(limit=200)
    by_type: dict[str, int] = {}
    for item in events:
        event_type = str(item.get("event_type") or "unknown")
        by_type[event_type] = by_type.get(event_type, 0) + 1
    return {
        "status": "ok",
        "event_count": len(events),
        "events_path": str(telemetry.events_path),
        "counts_by_type": by_type,
        "recent_events": events[-20:],
    }


@router.get("/system/audit-summary")
def get_audit_summary(request: Request) -> dict[str, object]:
    return AuditService(request.app.state.settings).get_summary()


@router.get("/system/audit-logs")
def get_audit_logs(request: Request, limit: int = 50) -> dict[str, object]:
    logs = AuditService(request.app.state.settings).list_logs(limit=limit)
    return {"status": "ok", "count": len(logs), "logs": logs}


@router.get("/system/specialist-summary")
def get_specialist_summary(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    telemetry = TelemetryService(settings)
    handoff_events = telemetry.list_events(event_type="agent_handoff", limit=500)
    orchestration_events = telemetry.list_events(event_type="agent_orchestration_summary", limit=200)
    counts_by_specialist: dict[str, int] = {}
    counts_by_workflow: dict[str, int] = {}
    recent_handoffs: list[dict[str, object]] = []

    for event in handoff_events:
        payload = event.get("payload") or {}
        specialist = str(payload.get("to_agent") or "unknown")
        counts_by_specialist[specialist] = counts_by_specialist.get(specialist, 0) + 1
        recent_handoffs.append(
            {
                "event_id": event.get("event_id"),
                "created_at": event.get("created_at"),
                "run_id": payload.get("run_id"),
                "trace_id": payload.get("trace_id"),
                "from_agent": payload.get("from_agent"),
                "to_agent": specialist,
                "capability": payload.get("capability"),
                "status": payload.get("status"),
            }
        )

    for event in orchestration_events:
        payload = event.get("payload") or {}
        workflow = str(payload.get("workflow") or "unknown")
        counts_by_workflow[workflow] = counts_by_workflow.get(workflow, 0) + 1

    return {
        "status": "ok",
        "counts_by_specialist": counts_by_specialist,
        "counts_by_workflow": counts_by_workflow,
        "recent_handoffs": recent_handoffs[-20:],
    }
