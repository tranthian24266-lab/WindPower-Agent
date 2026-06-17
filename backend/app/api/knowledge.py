from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.auth import require_write_api_key
from app.core.knowledge_ingestion import KnowledgeIngestionService
from app.core.knowledge_repository import KnowledgeRepository
from app.core.vector_index_service import VectorIndexService
from app.db.schemas import KnowledgeIngestionRequest, KnowledgeReindexRequest


router = APIRouter(tags=["knowledge"])


@router.post("/knowledge/ingest", dependencies=[Depends(require_write_api_key)])
def ingest_knowledge(request: Request, payload: KnowledgeIngestionRequest) -> dict[str, object]:
    settings = request.app.state.settings
    service = KnowledgeIngestionService(settings)
    try:
        if payload.include_defaults_only:
            return service.ingest_default_sources()
        return service.ingest_sources(service.discover_sources(), source_scope=payload.source_scope)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/knowledge/documents")
def list_knowledge_documents(request: Request) -> dict[str, object]:
    repository = KnowledgeRepository(request.app.state.settings.database_path)
    documents = repository.list_documents()
    return {"status": "ok", "count": len(documents), "documents": documents}


@router.get("/knowledge/chunks")
def list_knowledge_chunks(
    request: Request,
    document_id: Optional[str] = Query(default=None),
    task_type: Optional[str] = Query(default=None),
    source_type: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, object]:
    repository = KnowledgeRepository(request.app.state.settings.database_path)
    chunks = repository.list_chunks(
        document_id=document_id,
        task_type=task_type,
        source_type=source_type,
        limit=limit,
    )
    return {"status": "ok", "count": len(chunks), "chunks": chunks}


@router.get("/knowledge/ingestion-runs")
def list_ingestion_runs(request: Request) -> dict[str, object]:
    repository = KnowledgeRepository(request.app.state.settings.database_path)
    runs = repository.list_ingestion_runs()
    return {"status": "ok", "count": len(runs), "runs": runs}


@router.post("/knowledge/reindex", dependencies=[Depends(require_write_api_key)])
def reindex_knowledge(
    request: Request,
    payload: Optional[KnowledgeReindexRequest] = None,
) -> dict[str, object]:
    settings = request.app.state.settings
    service = VectorIndexService(settings)
    try:
        return service.reindex_all(force_recreate=(payload.force_recreate if payload is not None else False))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/knowledge/index-status")
def get_knowledge_index_status(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    service = VectorIndexService(settings)
    try:
        return service.get_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
