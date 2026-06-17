from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from app.core.auth import require_write_api_key
from app.core.report_generator import ReportGenerationError, ReportGeneratorService


router = APIRouter(tags=["reports"])


def _report_error_status(message: str) -> int:
    if message.startswith("Diagnosis case does not exist"):
        return 404
    if message.startswith("Report does not exist"):
        return 404
    return 500


@router.post("/reports/{case_id}/generate", dependencies=[Depends(require_write_api_key)])
def generate_report(request: Request, case_id: str) -> dict[str, object]:
    settings = request.app.state.settings
    service = ReportGeneratorService(settings)
    try:
        return service.generate(case_id)
    except ReportGenerationError as exc:
        status_code = _report_error_status(str(exc))
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("/reports/{case_id}")
def get_report(request: Request, case_id: str) -> dict[str, object]:
    settings = request.app.state.settings
    service = ReportGeneratorService(settings)
    try:
        return service.get_report(case_id)
    except ReportGenerationError as exc:
        status_code = _report_error_status(str(exc))
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("/reports/{case_id}/html", response_class=HTMLResponse)
def get_report_html(request: Request, case_id: str) -> HTMLResponse:
    settings = request.app.state.settings
    service = ReportGeneratorService(settings)
    try:
        report = service.get_report(case_id)
    except ReportGenerationError as exc:
        status_code = _report_error_status(str(exc))
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return HTMLResponse(report["html_content"])


@router.get("/reports/{case_id}/download")
def download_report(request: Request, case_id: str) -> FileResponse:
    settings = request.app.state.settings
    service = ReportGeneratorService(settings)
    try:
        report = service.get_report(case_id)
    except ReportGenerationError as exc:
        status_code = _report_error_status(str(exc))
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return FileResponse(
        report["report_html_path"],
        media_type="text/html",
        filename=f"{case_id}-report.html",
    )


@router.get("/reports/{case_id}/download/pdf")
def download_report_pdf(request: Request, case_id: str) -> FileResponse:
    settings = request.app.state.settings
    service = ReportGeneratorService(settings)
    try:
        report = service.get_report(case_id)
    except ReportGenerationError as exc:
        status_code = _report_error_status(str(exc))
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    pdf_path = report.get("report_pdf_path")
    if not pdf_path:
        raise HTTPException(
            status_code=404,
            detail=f"PDF report is not available for case_id '{case_id}': {report.get('pdf_reason') or 'pdf_not_generated'}",
        )

    resolved_pdf_path = Path(str(pdf_path))
    if not resolved_pdf_path.exists():
        raise HTTPException(status_code=404, detail=f"PDF report file does not exist for case_id '{case_id}'.")

    return FileResponse(
        resolved_pdf_path,
        media_type="application/pdf",
        filename=f"{case_id}-report.pdf",
    )
