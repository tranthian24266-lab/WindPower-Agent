from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse

from app.core.agents.orchestrator_agent import OrchestratorAgent
from app.core.agent_runtime.run_manager import RunManager
from app.core.agent_runtime.step_executor import StepExecutor
from app.core.agent_runtime.tool_registry import ToolRegistry
from app.core.audit_service import AuditService
from app.core.auth import get_actor_context, require_permissions
from app.core.enhanced_report_service import EnhancedReportService, EnhancedReportServiceError
from app.core.telemetry_service import TelemetryService


router = APIRouter(tags=["enhanced-reports"])


@router.post("/enhanced-reports/{case_id}/generate", dependencies=[Depends(require_permissions("enhanced_report:generate"))])
def generate_enhanced_report(request: Request, case_id: str) -> dict[str, object]:
    settings = request.app.state.settings
    actor = get_actor_context(request)
    orchestrator = OrchestratorAgent(settings)
    run_manager = RunManager(settings.database_path)
    run_id = run_manager.create_run(
        run_type="enhanced_report",
        case_id=case_id,
        input_payload={"case_id": case_id},
        triggered_by=actor.actor_id,
    )
    AuditService(settings).record(
        actor=actor,
        action="agent_run.create",
        resource_type="agent_run",
        resource_id=run_id,
        run_id=run_id,
        trace_id=(run_manager.get_run_detail(run_id) or {}).get("trace_id"),
        details={"run_type": "enhanced_report", "case_id": case_id},
    )
    tool_registry = ToolRegistry()
    tool_registry.register(
        "enhanced_report.generate",
        lambda: orchestrator.run_enhanced_report(run_id=run_id, case_id=case_id, actor=actor),
        allowed_run_types=("enhanced_report",),
    )
    executor = StepExecutor(run_manager, tool_registry, TelemetryService(settings))
    try:
        result = executor.execute_tool(
            run_id=run_id,
            step_name="enhanced_report.generate",
            tool_name="enhanced_report.generate",
            request_payload={"case_id": case_id},
        )
        return result
    except EnhancedReportServiceError as exc:
        run_manager.fail_run(
            run_id,
            error_payload={"type": exc.__class__.__name__, "message": str(exc)},
            current_step="enhanced_report.generate",
        )
        message = str(exc)
        if message.startswith("Diagnosis case does not exist"):
            status_code = 404
        elif message.startswith("Enhanced reports are disabled"):
            status_code = 409
        elif message.startswith("Enhanced report guardrail failed"):
            status_code = 422
        else:
            status_code = 500
        raise HTTPException(status_code=status_code, detail=message) from exc
    except Exception as exc:
        run_manager.fail_run(
            run_id,
            error_payload={"type": exc.__class__.__name__, "message": str(exc)},
            current_step="enhanced_report.generate",
        )
        raise


@router.get("/enhanced-reports/{case_id}")
def get_enhanced_report(
    request: Request,
    case_id: str,
    report_version_id: Optional[str] = Query(default=None),
) -> dict[str, object]:
    service = EnhancedReportService(request.app.state.settings)
    try:
        return service.get(case_id, report_version_id=report_version_id)
    except EnhancedReportServiceError as exc:
        message = str(exc)
        status_code = 404 if "does not exist" in message else 500
        raise HTTPException(status_code=status_code, detail=message) from exc


@router.get("/enhanced-reports/{case_id}/html", response_class=HTMLResponse)
def get_enhanced_report_html(
    request: Request,
    case_id: str,
    report_version_id: Optional[str] = Query(default=None),
) -> HTMLResponse:
    service = EnhancedReportService(request.app.state.settings)
    try:
        report = service.get(case_id, report_version_id=report_version_id)
    except EnhancedReportServiceError as exc:
        message = str(exc)
        status_code = 404 if "does not exist" in message else 500
        raise HTTPException(status_code=status_code, detail=message) from exc
    return HTMLResponse(report["html_content"] or "")


@router.get("/enhanced-reports/{case_id}/download/docx")
def download_enhanced_report_docx(
    request: Request,
    case_id: str,
    report_version_id: Optional[str] = Query(default=None),
) -> FileResponse:
    service = EnhancedReportService(request.app.state.settings)
    try:
        report = service.get(case_id, report_version_id=report_version_id)
    except EnhancedReportServiceError as exc:
        message = str(exc)
        status_code = 404 if "does not exist" in message else 500
        raise HTTPException(status_code=status_code, detail=message) from exc
    docx_path = report.get("report_docx_path")
    if not docx_path:
        raise HTTPException(status_code=404, detail=f"Enhanced report DOCX does not exist for case_id '{case_id}'.")
    return FileResponse(
        docx_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{case_id}-enhanced-report.docx",
    )


@router.get("/enhanced-reports/{case_id}/download/pdf")
def download_enhanced_report_pdf(
    request: Request,
    case_id: str,
    report_version_id: Optional[str] = Query(default=None),
) -> FileResponse:
    service = EnhancedReportService(request.app.state.settings)
    try:
        report = service.get(case_id, report_version_id=report_version_id)
    except EnhancedReportServiceError as exc:
        message = str(exc)
        status_code = 404 if "does not exist" in message else 500
        raise HTTPException(status_code=status_code, detail=message) from exc
    pdf_path = report.get("report_pdf_path")
    if not pdf_path:
        raise HTTPException(status_code=404, detail=f"Enhanced report PDF does not exist for case_id '{case_id}'.")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"{case_id}-enhanced-report.pdf",
    )


@router.get("/enhanced-reports/{case_id}/versions")
def list_enhanced_report_versions(request: Request, case_id: str) -> dict[str, object]:
    service = EnhancedReportService(request.app.state.settings)
    return service.list_versions(case_id)
