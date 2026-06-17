from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Any

from app.core.embedding_provider import EmbeddingProvider, build_embedding_provider
from app.core.knowledge_repository import KnowledgeRepository
from app.core.settings import Settings
from app.core.telemetry_service import TelemetryService
from app.core.vector_index_service import VectorIndexService


@dataclass
class RetrievalFilters:
    task_type: str | None = None
    component: str | None = None
    source_type: str | None = None
    model_family_id: str | None = None
    model_version_id: str | None = None


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    chunk_index: int
    content: str
    summary: str | None
    title: str
    source_path: str
    source_type: str
    task_type: str | None
    component: str | None
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_event_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["score"] = round(self.score, 6)
        return payload


@dataclass
class RetrievalResponse:
    results: list[RetrievedChunk]
    retrieval_event_id: str | None
    mode: str


class RetrievalService:
    def __init__(
        self,
        settings: Settings,
        repository: KnowledgeRepository | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        vector_index_service: VectorIndexService | None = None,
    ):
        self.settings = settings
        self.repository = repository or KnowledgeRepository(settings.database_path)
        selection = build_embedding_provider(
            settings.embedding_provider_name,
            model_name=settings.embedding_model_name,
        )
        self.embedding_provider = embedding_provider or selection.provider
        self.embedding_selection = selection
        self.vector_index_service = vector_index_service or VectorIndexService(
            settings,
            repository=self.repository,
            embedding_provider=self.embedding_provider,
        )
        self.telemetry = TelemetryService(settings)

    def search(
        self,
        query_text: str,
        *,
        case_id: str | None = None,
        task_type: str | None = None,
        component: str | None = None,
        source_type: str | None = None,
        model_family_id: str | None = None,
        model_version_id: str | None = None,
        top_k: int | None = None,
    ) -> RetrievalResponse:
        if not self.settings.knowledge_rag_enabled:
            response = RetrievalResponse(results=[], retrieval_event_id=None, mode="disabled")
            self._record_summary(
                query_text=query_text,
                case_id=case_id,
                task_type=task_type,
                top_k=top_k or self.settings.retrieval_top_k_default,
                response=response,
            )
            return response

        effective_top_k = min(top_k or self.settings.retrieval_top_k_default, self.settings.retrieval_top_k_max)
        filters = RetrievalFilters(
            task_type=task_type,
            component=component,
            source_type=source_type,
            model_family_id=model_family_id,
            model_version_id=model_version_id,
        )
        if self.settings.qdrant_enabled and self.settings.qdrant_prefer_remote:
            qdrant_response = self._search_qdrant(
                query_text=query_text,
                case_id=case_id,
                task_type=task_type,
                filters=filters,
                top_k=effective_top_k,
            )
            if qdrant_response is not None:
                self._record_summary(
                    query_text=query_text,
                    case_id=case_id,
                    task_type=task_type,
                    top_k=effective_top_k,
                    response=qdrant_response,
                )
                return qdrant_response

        local_response = self._search_local(
            query_text=query_text,
            case_id=case_id,
            task_type=task_type,
            filters=filters,
            top_k=effective_top_k,
        )
        if local_response.results:
            self._record_summary(
                query_text=query_text,
                case_id=case_id,
                task_type=task_type,
                top_k=effective_top_k,
                response=local_response,
            )
            return local_response

        qdrant_response = self._search_qdrant(
            query_text=query_text,
            case_id=case_id,
            task_type=task_type,
            filters=filters,
            top_k=effective_top_k,
        )
        if qdrant_response is not None:
            self._record_summary(
                query_text=query_text,
                case_id=case_id,
                task_type=task_type,
                top_k=effective_top_k,
                response=qdrant_response,
            )
            return qdrant_response
        self._record_summary(
            query_text=query_text,
            case_id=case_id,
            task_type=task_type,
            top_k=effective_top_k,
            response=local_response,
        )
        return local_response

    def _search_local(
        self,
        *,
        query_text: str,
        case_id: str | None,
        task_type: str | None,
        filters: RetrievalFilters,
        top_k: int,
    ) -> RetrievalResponse:
        candidates = self.repository.list_chunks(
            task_type=filters.task_type,
            component=filters.component,
            source_type=filters.source_type,
            model_family_id=filters.model_family_id,
            model_version_id=filters.model_version_id,
        )
        if not candidates:
            retrieval_event_id = self.repository.record_retrieval_event(
                case_id=case_id,
                query_text=query_text,
                task_type=task_type,
                top_k=top_k,
                filters=asdict(filters),
                results=[],
            )
            return RetrievalResponse(results=[], retrieval_event_id=retrieval_event_id, mode="no_results")

        query_embedding = self.embedding_provider.embed_query(query_text)
        content_embeddings = self.embedding_provider.embed_documents([item["content"] for item in candidates])
        query_words = {word for word in query_text.lower().split() if word}

        results: list[RetrievedChunk] = []
        for candidate, embedding in zip(candidates, content_embeddings):
            score = self._cosine_similarity(query_embedding, embedding)
            if task_type and candidate.get("task_type") == task_type:
                score += 0.08
            if query_words and candidate.get("keywords"):
                keyword_hits = len(query_words.intersection(set(candidate["keywords"])))
                score += min(keyword_hits * 0.03, 0.12)
            if score < self.settings.retrieval_min_score:
                continue
            results.append(
                RetrievedChunk(
                    chunk_id=str(candidate["chunk_id"]),
                    document_id=str(candidate["document_id"]),
                    chunk_index=int(candidate["chunk_index"]),
                    content=str(candidate["content"]),
                    summary=candidate.get("summary"),
                    title=str(candidate["title"]),
                    source_path=str(candidate["source_path"]),
                    source_type=str(candidate["source_type"]),
                    task_type=candidate.get("task_type"),
                    component=candidate.get("component"),
                    score=score,
                    metadata=dict(candidate.get("metadata") or {}),
                )
            )

        results.sort(key=lambda item: item.score, reverse=True)
        trimmed = results[:top_k]
        retrieval_event_id = self.repository.record_retrieval_event(
            case_id=case_id,
            query_text=query_text,
            task_type=task_type,
            top_k=top_k,
            filters=asdict(filters),
            results=[item.to_event_payload() for item in trimmed],
        )
        return RetrievalResponse(results=trimmed, retrieval_event_id=retrieval_event_id, mode="local_dense")

    def _search_qdrant(
        self,
        *,
        query_text: str,
        case_id: str | None,
        task_type: str | None,
        filters: RetrievalFilters,
        top_k: int,
    ) -> RetrievalResponse | None:
        if not self.settings.qdrant_enabled:
            return None
        vector_response = self.vector_index_service.search(
            query_text=query_text,
            filters={
                "task_type": filters.task_type,
                "component": filters.component,
                "source_type": filters.source_type,
                "model_family_id": filters.model_family_id,
                "model_version_id": filters.model_version_id,
            },
            top_k=top_k,
        )
        if vector_response.status != "ok":
            return None

        chunks: list[RetrievedChunk] = []
        for payload in vector_response.results:
            metadata = dict(payload.get("metadata") or {})
            chunks.append(
                RetrievedChunk(
                    chunk_id=str(payload.get("chunk_id")),
                    document_id=str(payload.get("document_id") or metadata.get("document_id") or ""),
                    chunk_index=int(payload.get("chunk_index") or metadata.get("chunk_index") or 0),
                    content=str(payload.get("content") or ""),
                    summary=payload.get("summary"),
                    title=str(payload.get("title") or metadata.get("title") or ""),
                    source_path=str(payload.get("source_path") or metadata.get("source_path") or ""),
                    source_type=str(payload.get("source_type") or metadata.get("source_type") or ""),
                    task_type=payload.get("task_type") or metadata.get("task_type"),
                    component=payload.get("component") or metadata.get("component"),
                    score=float(payload.get("score") or 0.0),
                    metadata=metadata,
                )
            )

        retrieval_event_id = self.repository.record_retrieval_event(
            case_id=case_id,
            query_text=query_text,
            task_type=task_type,
            top_k=top_k,
            filters=asdict(filters),
            results=[item.to_event_payload() for item in chunks],
        )
        return RetrievalResponse(results=chunks, retrieval_event_id=retrieval_event_id, mode="qdrant_dense")

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        if len(left) != len(right) or not left or not right:
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)

    def _record_summary(
        self,
        *,
        query_text: str,
        case_id: str | None,
        task_type: str | None,
        top_k: int,
        response: RetrievalResponse,
    ) -> None:
        self.telemetry.record(
            "retrieval_summary",
            {
                "case_id": case_id,
                "task_type": task_type,
                "query_preview": query_text[:160],
                "top_k": top_k,
                "actual_hits": len(response.results),
                "retrieval_mode": response.mode,
                "retrieval_event_id": response.retrieval_event_id,
            },
        )
