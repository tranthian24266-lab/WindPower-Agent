from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Optional

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "风电小模型库智能诊断平台"
    api_prefix: str = "/api"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"])
    backend_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2])
    littlemodel_root: Optional[Path] = Field(
        default=None,
        validation_alias=AliasChoices("WINDPOWER_LITTLEMODEL_ROOT", "LITTLEMODEL_ROOT"),
    )
    model_catalog_enabled: bool = True
    model_sync_on_startup: bool = True
    model_router_fallback_to_v1: bool = True
    model_catalog_default_alias: str = "default"
    model_catalog_page_size_default: int = 20
    model_catalog_page_size_max: int = 100
    model_validation_timeout_seconds: float = 120.0
    model_package_max_upload_bytes: int = 1024 * 1024 * 1024
    model_package_max_uncompressed_bytes: int = 2 * 1024 * 1024 * 1024
    model_package_max_files: int = 2000
    auth_enabled: bool = False
    api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("WINDPOWER_API_KEY", "API_KEY"),
    )
    database_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("WINDPOWER_DATABASE_URL", "DATABASE_URL"),
    )
    db_pool_size: int = 20
    db_max_overflow: int = 10
    rbac_enabled: bool = False
    default_actor_role: str = "operator"
    audit_enabled: bool = True
    agent_mode: str = "auto"
    deepseek_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("WINDPOWER_DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY"),
    )
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        validation_alias=AliasChoices("WINDPOWER_DEEPSEEK_BASE_URL", "DEEPSEEK_BASE_URL"),
    )
    deepseek_model_name: str = Field(
        default="deepseek-v4-pro",
        validation_alias=AliasChoices("WINDPOWER_DEEPSEEK_MODEL_NAME", "DEEPSEEK_MODEL_NAME"),
    )
    deepseek_timeout_seconds: float = 60.0
    deepseek_thinking_enabled: bool = True
    deepseek_reasoning_effort: str = "high"
    deepseek_chat_json_output_enabled: bool = False
    deepseek_max_tokens_chat: int = 1200
    enhanced_report_llm_enabled: bool = True
    deepseek_reasoning_effort_report: str = "high"
    deepseek_max_tokens_report: int = 2400
    enhanced_report_json_retry_count: int = 2
    base_report_pdf_enabled: bool = True
    enhanced_report_pdf_enabled: bool = True
    enhanced_report_pdf_backend: str = "reportlab"
    observability_enabled: bool = True
    knowledge_rag_enabled: bool = False
    knowledge_ingestion_enabled: bool = False
    chat_rag_enabled: bool = False
    knowledge_case_ingestion_enabled: bool = False
    enhanced_reports_enabled: bool = False
    qdrant_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("WINDPOWER_QDRANT_ENABLED", "QDRANT_ENABLED"),
    )
    qdrant_prefer_remote: bool = False
    qdrant_recreate_collection_on_rebuild: bool = False
    qdrant_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("WINDPOWER_QDRANT_URL", "QDRANT_URL"),
    )
    qdrant_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("WINDPOWER_QDRANT_API_KEY", "QDRANT_API_KEY"),
    )
    qdrant_collection_name: str = Field(
        default="knowledge_chunks",
        validation_alias=AliasChoices("WINDPOWER_QDRANT_COLLECTION_NAME", "QDRANT_COLLECTION_NAME"),
    )
    embedding_provider_name: str = "local_ngram"
    embedding_model_name: str = "char-ngram-v1"
    embedding_batch_size: int = 32
    retrieval_top_k_default: int = 4
    retrieval_top_k_max: int = 8
    retrieval_min_score: float = 0.08
    rag_max_citations: int = 3
    agent_async_enabled: bool = True
    embedded_worker_enabled: bool = True
    worker_poll_interval_ms: int = 500
    worker_lease_seconds: int = 300
    worker_stale_timeout_seconds: int = 360
    worker_max_attempts: int = 1

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="WINDPOWER_",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("littlemodel_root", mode="before")
    @classmethod
    def normalize_littlemodel_root(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            return Path(stripped).expanduser()
        if isinstance(value, Path):
            return value.expanduser()
        return value

    @field_validator("deepseek_reasoning_effort", "deepseek_reasoning_effort_report")
    @classmethod
    def normalize_reasoning_effort(cls, value: str) -> str:
        normalized = (value or "high").strip().lower()
        if normalized in {"low", "medium", "high"}:
            return "high"
        if normalized in {"xhigh", "max"}:
            return "max"
        return "high"

    @field_validator("enhanced_report_pdf_backend")
    @classmethod
    def normalize_pdf_backend(cls, value: str) -> str:
        normalized = (value or "reportlab").strip().lower()
        if normalized in {"reportlab", "disabled"}:
            return normalized
        return "reportlab"

    @property
    def uploads_path(self) -> Path:
        return self.backend_root / "uploads"

    @property
    def model_package_staging_path(self) -> Path:
        return self.uploads_path / "model_packages" / "staging"

    @property
    def model_package_trash_path(self) -> Path:
        return self.uploads_path / "model_packages" / "trash"

    @property
    def outputs_path(self) -> Path:
        return self.backend_root / "outputs"

    @property
    def reports_path(self) -> Path:
        return self.backend_root / "reports"

    @property
    def telemetry_path(self) -> Path:
        return self.outputs_path / "telemetry"

    @property
    def eval_outputs_path(self) -> Path:
        return self.outputs_path / "evals"

    @property
    def database_path(self) -> Path:
        return self.backend_root / "windpower.db"

    @property
    def templates_path(self) -> Path:
        candidate = self.backend_root / "templates"
        if candidate.exists():
            return candidate
        return Path(__file__).resolve().parents[2] / "templates"

    @property
    def eval_suites_path(self) -> Path:
        candidate = self.backend_root / "evals" / "suites"
        if candidate.exists():
            return candidate
        return Path(__file__).resolve().parents[2] / "evals" / "suites"

    @property
    def project_root(self) -> Path:
        return self.backend_root.parent

    @property
    def knowledge_base_path(self) -> Path:
        candidate = self.project_root / "knowledge_base"
        if candidate.exists():
            return candidate
        return Path(__file__).resolve().parents[3] / "knowledge_base"

    @property
    def knowledge_raw_path(self) -> Path:
        return self.knowledge_base_path / "raw"

    @property
    def knowledge_processed_path(self) -> Path:
        return self.knowledge_base_path / "processed"

    @property
    def knowledge_index_manifest_path(self) -> Path:
        return self.knowledge_base_path / "index_manifest"

    @property
    def resolved_littlemodel_root(self) -> Path:
        candidates: list[Path] = []
        if self.littlemodel_root is not None:
            candidates.append(self.littlemodel_root)

        bundled = self.project_root / "littlemodel"
        if all(candidate != bundled for candidate in candidates):
            candidates.append(bundled)

        sibling = self.project_root.parent / "littlemodel"
        if all(candidate != sibling for candidate in candidates):
            candidates.append(sibling)

        for candidate in candidates:
            resolved = candidate.resolve(strict=False)
            if resolved.exists():
                return resolved

        checked_candidates = ", ".join(str(candidate.resolve(strict=False)) for candidate in candidates)
        raise RuntimeError(
            "Unable to locate the littlemodel workspace. Configure WINDPOWER_LITTLEMODEL_ROOT "
            f"(or legacy LITTLEMODEL_ROOT). Checked: {checked_candidates}"
        )


@lru_cache
def load_settings() -> Settings:
    return Settings()
