from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agent_runs import router as agent_runs_router
from app.api.cases import router as cases_router
from app.api.chat import router as chat_router
from app.api.enhanced_reports import router as enhanced_reports_router
from app.api.evals import router as evals_router
from app.api.knowledge import router as knowledge_router
from app.api.model_catalog import router as model_catalog_router
from app.core.case_store import CaseStoreService
from app.api.diagnose import router as diagnose_router
from app.api.health import router as health_router
from app.api.models import router as models_router
from app.api.reviews import router as reviews_router
from app.api.reports import router as reports_router
from app.api.system import router as system_router
from app.api.upload import router as upload_router
from app.db.database import Database
from app.jobs.worker_runtime import AgentWorker
from app.core.model_sync import ModelSyncError, ModelSyncService
from app.core.settings import Settings, load_settings


LOGGER = logging.getLogger(__name__)


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    _configure_logging()
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        worker = None
        if settings.agent_async_enabled and settings.embedded_worker_enabled:
            worker = AgentWorker(settings, worker_id="embedded")
            worker.start()
            app.state.agent_worker = worker
        try:
            yield
        finally:
            existing_worker = worker or getattr(app.state, "agent_worker", None)
            if existing_worker is not None:
                existing_worker.stop()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    Database.configure_default_database_url(settings.database_url)
    settings.resolved_littlemodel_root
    settings.uploads_path.mkdir(parents=True, exist_ok=True)
    settings.outputs_path.mkdir(parents=True, exist_ok=True)
    settings.reports_path.mkdir(parents=True, exist_ok=True)
    settings.templates_path.mkdir(parents=True, exist_ok=True)
    settings.knowledge_base_path.mkdir(parents=True, exist_ok=True)
    settings.knowledge_raw_path.mkdir(parents=True, exist_ok=True)
    settings.knowledge_processed_path.mkdir(parents=True, exist_ok=True)
    settings.knowledge_index_manifest_path.mkdir(parents=True, exist_ok=True)
    CaseStoreService(settings.database_path)
    _sync_model_catalog_on_startup(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix=settings.api_prefix)
    app.include_router(system_router, prefix=settings.api_prefix)
    app.include_router(agent_runs_router, prefix=settings.api_prefix)
    app.include_router(models_router, prefix=settings.api_prefix)
    app.include_router(model_catalog_router, prefix=settings.api_prefix)
    app.include_router(upload_router, prefix=settings.api_prefix)
    app.include_router(diagnose_router, prefix=settings.api_prefix)
    app.include_router(cases_router, prefix=settings.api_prefix)
    app.include_router(reports_router, prefix=settings.api_prefix)
    app.include_router(reviews_router, prefix=settings.api_prefix)
    app.include_router(enhanced_reports_router, prefix=settings.api_prefix)
    app.include_router(evals_router, prefix=settings.api_prefix)
    app.include_router(chat_router, prefix=settings.api_prefix)
    app.include_router(knowledge_router, prefix=settings.api_prefix)

    @app.get("/", tags=["system"])
    def root() -> dict[str, str]:
        return {"status": "ok", "message": settings.app_name}

    return app


def _sync_model_catalog_on_startup(settings: Settings) -> None:
    if not settings.model_catalog_enabled or not settings.model_sync_on_startup:
        return

    try:
        result = ModelSyncService(
            settings.database_path,
            settings.resolved_littlemodel_root,
            default_alias=settings.model_catalog_default_alias,
        ).sync_registry()
    except ModelSyncError as exc:
        if not settings.model_router_fallback_to_v1:
            raise
        LOGGER.warning("Model catalog sync failed during startup, continuing with V1 fallback: %s", exc)
        return

    LOGGER.info(
        "Model catalog synced during startup: discovered=%s upserted=%s status=%s",
        result.discovered_count,
        result.upserted_count,
        result.status,
    )


app = create_app()
