from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from app.core.auth import require_write_api_key
from app.core.case_store import CaseStoreService
from app.core.file_manager import FileManagerError, FileManagerService


router = APIRouter(tags=["files"])


@router.post("/upload", dependencies=[Depends(require_write_api_key)])
async def upload_file(request: Request, file: UploadFile = File(...)) -> dict[str, object]:
    settings = request.app.state.settings
    service = FileManagerService(settings.uploads_path)
    store = CaseStoreService(settings.database_path)
    try:
        metadata = await service.save_upload(file)
    except FileManagerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    store.save_uploaded_file(metadata)

    return {"status": "ok", "file": metadata}


@router.get("/files/{file_id}")
def get_file_metadata(request: Request, file_id: str) -> dict[str, object]:
    settings = request.app.state.settings
    service = FileManagerService(settings.uploads_path)
    try:
        metadata = service.get_file_metadata(file_id)
    except FileManagerError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"status": "ok", "file": metadata}
