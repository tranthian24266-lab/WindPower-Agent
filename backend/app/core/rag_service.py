from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.core.retrieval_service import RetrievedChunk, RetrievalResponse, RetrievalService
from app.core.settings import Settings


@dataclass
class RagAnswer:
    answer: str
    mode: str
    citations: list[dict[str, Any]]
    retrieved_chunks: list[dict[str, Any]]
    retrieval_event_id: str | None
    knowledge_mode: str


class RAGService:
    def __init__(self, settings: Settings, retrieval_service: RetrievalService | None = None):
        self.settings = settings
        self.retrieval_service = retrieval_service or RetrievalService(settings)

    def answer(
        self,
        *,
        case: dict[str, Any],
        model_meta: dict[str, Any],
        question: str,
        answer_builder: Callable[[str | None], tuple[str, str]],
    ) -> RagAnswer:
        if not self.settings.chat_rag_enabled or not self.settings.knowledge_rag_enabled:
            answer, mode = answer_builder(None)
            return RagAnswer(
                answer=answer,
                mode=mode,
                citations=[],
                retrieved_chunks=[],
                retrieval_event_id=None,
                knowledge_mode="disabled",
            )

        try:
            retrieval = self.retrieval_service.search(
                question,
                case_id=case["case_id"],
                task_type=case["task_type"],
                model_version_id=model_meta.get("model_version_id"),
            )
        except Exception:
            answer, mode = answer_builder(None)
            return RagAnswer(
                answer=answer,
                mode=mode,
                citations=[],
                retrieved_chunks=[],
                retrieval_event_id=None,
                knowledge_mode="rag_error_fallback",
            )

        knowledge_context = self._build_knowledge_context(retrieval)
        answer, base_mode = answer_builder(knowledge_context)
        mode = f"rag_{base_mode}" if retrieval.results else base_mode
        return RagAnswer(
            answer=answer,
            mode=mode,
            citations=self._build_citations(retrieval.results),
            retrieved_chunks=[self._serialize_chunk(chunk) for chunk in retrieval.results],
            retrieval_event_id=retrieval.retrieval_event_id,
            knowledge_mode=retrieval.mode,
        )

    def _build_knowledge_context(self, retrieval: RetrievalResponse) -> str | None:
        if not retrieval.results:
            return None
        parts = []
        for chunk in retrieval.results[: self.settings.rag_max_citations]:
            parts.append(f"[{chunk.title}#{chunk.chunk_index}] {chunk.content}")
        return "\n\n".join(parts)

    def _build_citations(self, chunks: list[RetrievedChunk]) -> list[dict[str, Any]]:
        citations: list[dict[str, Any]] = []
        for chunk in chunks[: self.settings.rag_max_citations]:
            citations.append(
                {
                    "document_id": chunk.document_id,
                    "chunk_id": chunk.chunk_id,
                    "title": chunk.title,
                    "source_path": chunk.source_path,
                    "source_type": chunk.source_type,
                    "chunk_index": chunk.chunk_index,
                    "summary": chunk.summary or chunk.content[:160],
                    "score": round(chunk.score, 6),
                }
            )
        return citations

    def _serialize_chunk(self, chunk: RetrievedChunk) -> dict[str, Any]:
        return {
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "summary": chunk.summary,
            "title": chunk.title,
            "source_path": chunk.source_path,
            "source_type": chunk.source_type,
            "task_type": chunk.task_type,
            "component": chunk.component,
            "score": round(chunk.score, 6),
            "metadata": chunk.metadata,
        }
