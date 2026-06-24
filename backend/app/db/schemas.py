from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class DiagnoseRequest(BaseModel):
    file_id: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    options: Optional[Dict[str, Any]] = None


class AutoDiagnoseRequest(BaseModel):
    file_id: str = Field(min_length=1)
    confirmed_task_type: Optional[str] = None
    options: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    case_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    session_id: Optional[str] = None


class KnowledgeIngestionRequest(BaseModel):
    source_scope: str = Field(default="all")
    include_defaults_only: bool = False


class KnowledgeReindexRequest(BaseModel):
    force_recreate: bool = False


class ModelAliasUpdateRequest(BaseModel):
    model_version_id: str = Field(min_length=1)
    reason: Optional[str] = None


class AgentRunCreateRequest(BaseModel):
    run_type: str = Field(min_length=1)
    case_id: Optional[str] = None
    session_id: Optional[str] = None
    input: Dict[str, Any] = Field(default_factory=dict)


class ReviewDecisionRequest(BaseModel):
    reviewer: Optional[str] = None
    comment: Optional[str] = None
