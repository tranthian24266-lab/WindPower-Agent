from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from app.core.case_store import CaseStoreError, CaseStoreService
from app.core.embedding_provider import EmbeddingProvider, build_embedding_provider
from app.core.knowledge_repository import (
    KnowledgeChunkRecord,
    KnowledgeDocumentRecord,
    KnowledgeRepository,
)
from app.core.settings import Settings
from app.core.vector_index_service import VectorIndexService


@dataclass
class KnowledgeSource:
    source_path: Path
    source_type: str
    title: str
    task_type: str | None = None
    component: str | None = None
    language: str | None = "zh"
    subtask_type: str | None = None
    model_family_id: str | None = None
    model_version_id: str | None = None
    source_identity: str | None = None
    content_override: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class KnowledgeIngestionService:
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

    def ingest_default_sources(self) -> dict[str, Any]:
        if not self.settings.knowledge_ingestion_enabled:
            return {
                "status": "skipped",
                "reason": "knowledge_ingestion_disabled",
                "discovered_count": 0,
                "processed_count": 0,
                "failed_count": 0,
            }
        return self.ingest_sources(self.discover_sources(), source_scope="knowledge_base")

    def discover_sources(self) -> list[KnowledgeSource]:
        sources: list[KnowledgeSource] = []
        sources.extend(self._discover_knowledge_base_sources())
        sources.extend(self._discover_littlemodel_sources())
        sources.extend(self._discover_case_sources())
        return sources

    def ingest_sources(self, sources: list[KnowledgeSource], *, source_scope: str) -> dict[str, Any]:
        if not self.settings.knowledge_ingestion_enabled:
            return {
                "status": "skipped",
                "reason": "knowledge_ingestion_disabled",
                "discovered_count": 0,
                "processed_count": 0,
                "failed_count": 0,
            }
        self._ensure_directories()
        ingestion_run_id = self.repository.start_ingestion_run(source_scope)
        processed_count = 0
        failed_count = 0
        details: dict[str, Any] = {"documents": []}

        for source in sources:
            try:
                details["documents"].append(self._ingest_single_source(source))
                processed_count += 1
            except Exception as exc:  # pragma: no cover - defensive accounting
                failed_count += 1
                details["documents"].append(
                    {
                        "source_path": str(source.source_path),
                        "status": "failed",
                        "error": str(exc),
                    }
                )

        status = "completed" if failed_count == 0 else "completed_with_errors"
        self.repository.finish_ingestion_run(
            ingestion_run_id,
            status=status,
            discovered_count=len(sources),
            processed_count=processed_count,
            failed_count=failed_count,
            details=details,
        )
        return {
            "status": status,
            "ingestion_run_id": ingestion_run_id,
            "discovered_count": len(sources),
            "processed_count": processed_count,
            "failed_count": failed_count,
            "details": details,
        }

    def _ingest_single_source(self, source: KnowledgeSource) -> dict[str, Any]:
        content = self._load_source_text(source)
        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
        document_id = self._document_id_for(source)
        metadata = dict(source.metadata)
        metadata["checksum_sha256"] = checksum

        document = KnowledgeDocumentRecord(
            document_id=document_id,
            source_type=source.source_type,
            source_path=str(source.source_path),
            title=source.title,
            task_type=source.task_type,
            subtask_type=source.subtask_type,
            component=source.component,
            model_family_id=source.model_family_id,
            model_version_id=source.model_version_id,
            language=source.language,
            checksum=checksum,
            metadata=metadata,
        )
        chunks = self._build_chunks(document, content)
        index_summary = self.vector_index_service.sync_document_chunks(document, chunks)
        self.repository.upsert_document(document)
        self.repository.replace_chunks(document.document_id, chunks)
        self._write_processed_artifacts(document, chunks)

        return {
            "document_id": document.document_id,
            "source_path": str(source.source_path),
            "status": "completed",
            "chunk_count": len(chunks),
            "index_summary": index_summary,
        }

    def _build_chunks(self, document: KnowledgeDocumentRecord, content: str) -> list[KnowledgeChunkRecord]:
        sections = self._split_sections(content)
        chunks: list[KnowledgeChunkRecord] = []
        for chunk_index, section in enumerate(sections):
            text = section.strip()
            if not text:
                continue
            citation = {
                "document_id": document.document_id,
                "source_path": document.source_path,
                "title": document.title,
                "chunk_index": chunk_index,
            }
            metadata = {
                "task_type": document.task_type,
                "component": document.component,
                "source_type": document.source_type,
                "document_id": document.document_id,
                "source_path": document.source_path,
                "title": document.title,
                "chunk_index": chunk_index,
            }
            chunks.append(
                KnowledgeChunkRecord(
                    chunk_id=self._chunk_id_for(document.document_id, chunk_index),
                    document_id=document.document_id,
                    chunk_index=chunk_index,
                    content=text,
                    summary=text[:180],
                    tokens_estimate=max(1, len(text) // 4),
                    keywords=self._extract_keywords(text),
                    citations=[citation],
                    metadata=metadata,
                )
            )
        return chunks

    def _split_sections(self, content: str) -> list[str]:
        normalized = content.replace("\r\n", "\n")
        raw_sections = re.split(r"\n(?=#)", normalized)
        sections: list[str] = []
        for raw in raw_sections:
            paragraphs = [line.strip() for line in raw.splitlines() if line.strip()]
            if not paragraphs:
                continue
            current: list[str] = []
            current_length = 0
            for paragraph in paragraphs:
                projected = current_length + len(paragraph)
                if current and projected > 900:
                    sections.append("\n".join(current))
                    overlap = current[-1:] if len(current[-1]) < 180 else []
                    current = overlap + [paragraph]
                    current_length = sum(len(item) for item in current)
                    continue
                current.append(paragraph)
                current_length += len(paragraph)
            if current:
                sections.append("\n".join(current))
        return sections

    def _extract_keywords(self, text: str) -> list[str]:
        words = [token.strip(".,:;!?()[]{}<>`'\"") for token in text.lower().split()]
        keywords: list[str] = []
        for word in words:
            if len(word) < 4 or word in keywords:
                continue
            keywords.append(word)
            if len(keywords) >= 8:
                break
        return keywords

    def _document_id_for(self, source: KnowledgeSource) -> str:
        identity = source.source_identity or self._source_identity(source.source_path)
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]

    def _chunk_id_for(self, document_id: str, chunk_index: int) -> str:
        identity = f"{document_id}:{chunk_index}"
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]

    def _load_source_text(self, source: KnowledgeSource) -> str:
        if source.content_override is not None:
            return source.content_override
        if source.source_path.suffix.lower() == ".json":
            payload = json.loads(source.source_path.read_text(encoding="utf-8"))
            return self._json_to_text(payload, heading=source.title)
        return source.source_path.read_text(encoding="utf-8")

    def _json_to_text(self, payload: Any, *, heading: str) -> str:
        lines = [f"# {heading}"]
        self._append_json_lines(lines, payload, depth=0)
        return "\n".join(lines)

    def _append_json_lines(self, lines: list[str], payload: Any, *, depth: int) -> None:
        prefix = "  " * depth
        if isinstance(payload, dict):
            for key, value in payload.items():
                if isinstance(value, (dict, list)):
                    lines.append(f"{prefix}- {key}:")
                    self._append_json_lines(lines, value, depth=depth + 1)
                else:
                    lines.append(f"{prefix}- {key}: {value}")
            return
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, (dict, list)):
                    lines.append(f"{prefix}- item:")
                    self._append_json_lines(lines, item, depth=depth + 1)
                else:
                    lines.append(f"{prefix}- {item}")
            return
        lines.append(f"{prefix}- {payload}")

    def _discover_knowledge_base_sources(self) -> list[KnowledgeSource]:
        sources: list[KnowledgeSource] = []
        mapping = [
            (self.settings.knowledge_base_path / "domain_knowledge", "domain_markdown"),
            (self.settings.knowledge_base_path / "models", "model_markdown"),
        ]

        for directory, source_type in mapping:
            if not directory.exists():
                continue
            for path in sorted(directory.glob("*.md")):
                task_type = path.stem
                sources.append(
                    KnowledgeSource(
                        source_path=path,
                        source_type=source_type,
                        title=path.stem.replace("_", " "),
                        task_type=task_type,
                        component="knowledge_base",
                        metadata={"relative_path": self._safe_relative_path(path)},
                    )
                )

        raw_root = self.settings.knowledge_raw_path
        if raw_root.exists():
            for path in sorted(raw_root.rglob("*.md")):
                relative = path.relative_to(raw_root)
                sources.append(
                    KnowledgeSource(
                        source_path=path,
                        source_type=f"curated_{relative.parts[0]}",
                        title=path.stem.replace("_", " "),
                        task_type=self._task_type_from_name(path.stem),
                        component="curated_knowledge",
                        metadata={"relative_path": self._safe_relative_path(path)},
                    )
                )
        return sources

    def _discover_littlemodel_sources(self) -> list[KnowledgeSource]:
        sources: list[KnowledgeSource] = []
        task_directories = {
            "fault_diagnosis": self.settings.resolved_littlemodel_root / "fault_diagnosis",
            "rul_prediction": self.settings.resolved_littlemodel_root / "rul_prediction",
            "anomaly_detection": self.settings.resolved_littlemodel_root / "anomaly_detection",
        }
        summary_names = {"reproduce_summary.md", "final_summary.md", "original_README.md"}

        for task_type, root in task_directories.items():
            if not root.exists():
                continue

            readme_path = root / "README.md"
            if readme_path.exists():
                sources.append(
                    KnowledgeSource(
                        source_path=readme_path,
                        source_type="littlemodel_readme",
                        title=f"{task_type} readme",
                        task_type=task_type,
                        component="littlemodel",
                        metadata={"relative_path": self._safe_relative_path(readme_path)},
                    )
                )

            model_card_path = root / "model_card.json"
            if model_card_path.exists():
                model_card = json.loads(model_card_path.read_text(encoding="utf-8"))
                sources.append(
                    KnowledgeSource(
                        source_path=model_card_path,
                        source_type="littlemodel_model_card",
                        title=f"{task_type} model card",
                        task_type=task_type,
                        component="littlemodel",
                        model_version_id=str(model_card.get("model_id") or ""),
                        metadata={
                            "relative_path": self._safe_relative_path(model_card_path),
                            "paper_title": model_card.get("paper_title"),
                            "dataset": model_card.get("dataset"),
                        },
                    )
                )

            docs_dir = root / "docs"
            if docs_dir.exists():
                for path in sorted(docs_dir.iterdir()):
                    if not path.is_file() or path.name not in summary_names:
                        continue
                    sources.append(
                        KnowledgeSource(
                            source_path=path,
                            source_type="littlemodel_summary",
                            title=f"{task_type} {path.stem}",
                            task_type=task_type,
                            component="littlemodel_docs",
                            metadata={"relative_path": self._safe_relative_path(path)},
                        )
                    )
        return sources

    def _task_type_from_name(self, name: str) -> str | None:
        for task_type in ("fault_diagnosis", "rul_prediction", "anomaly_detection"):
            if task_type in name:
                return task_type
        return None

    def _discover_case_sources(self) -> list[KnowledgeSource]:
        if not self.settings.knowledge_case_ingestion_enabled:
            return []

        case_store = CaseStoreService(self.settings.database_path)
        sources: list[KnowledgeSource] = []
        try:
            cases = case_store.list_cases()
        except CaseStoreError:
            return []

        for case in cases:
            case_id = str(case["case_id"])
            try:
                detail = case_store.get_case_detail(case_id)
            except CaseStoreError:
                continue
            sources.append(
                KnowledgeSource(
                    source_path=Path(f"historical_cases/{case_id}.md"),
                    source_type="historical_case_summary",
                    title=f"{detail['task_type']} case {case_id}",
                    task_type=detail.get("task_type"),
                    component="case_history",
                    model_version_id=detail.get("model_id"),
                    source_identity=f"case://{case_id}",
                    content_override=self._build_case_summary_content(detail),
                    metadata={
                        "case_id": case_id,
                        "risk_level": detail.get("risk_level"),
                        "model_id": detail.get("model_id"),
                        "created_at": detail.get("created_at"),
                    },
                )
            )
        return sources

    def _build_case_summary_content(self, case: dict[str, Any]) -> str:
        result = dict(case.get("result") or {})
        summary = result.get("summary") or ""
        recommendation = result.get("recommendation") or ""
        metrics = self._format_case_metrics(case.get("task_type"), result)
        lines = [
            f"# Historical Case {case['case_id']}",
            "",
            f"- Task type: {case.get('task_type')}",
            f"- Model id: {case.get('model_id')}",
            f"- Risk level: {case.get('risk_level')}",
            f"- Created at: {case.get('created_at')}",
        ]
        if case.get("original_filename"):
            lines.append(f"- Original filename: {case.get('original_filename')}")
        if summary:
            lines.extend(["", "## Summary", "", str(summary)])
        if recommendation:
            lines.extend(["", "## Recommendation", "", str(recommendation)])
        if metrics:
            lines.extend(["", "## Key Metrics", ""])
            lines.extend(f"- {item}" for item in metrics)
        lines.extend(["", "## Result Snapshot", "", self._json_to_text(result, heading="result")])
        return "\n".join(lines)

    def _format_case_metrics(self, task_type: Any, result: dict[str, Any]) -> list[str]:
        if task_type == "fault_diagnosis":
            return [
                f"prediction: {result.get('prediction')}",
                f"confidence: {result.get('confidence')}",
                f"risk_level: {result.get('risk_level')}",
            ]
        if task_type == "rul_prediction":
            return [
                f"rul_raw: {result.get('rul_raw')}",
                f"rul_clipped: {result.get('rul_clipped')}",
                f"risk_level: {result.get('risk_level')}",
            ]
        if task_type == "anomaly_detection":
            return [
                f"anomaly_ratio: {result.get('anomaly_ratio')}",
                f"num_anomalies: {result.get('num_anomalies')}",
                f"risk_level: {result.get('risk_level')}",
            ]
        metrics: list[str] = []
        for key, value in result.items():
            if isinstance(value, (dict, list)):
                continue
            metrics.append(f"{key}: {value}")
            if len(metrics) >= 6:
                break
        return metrics

    def _safe_relative_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.settings.project_root))
        except ValueError:
            return str(path)

    def _source_identity(self, path: Path) -> str:
        return self._safe_relative_path(path)

    def _ensure_directories(self) -> None:
        self.settings.knowledge_raw_path.mkdir(parents=True, exist_ok=True)
        self.settings.knowledge_processed_path.mkdir(parents=True, exist_ok=True)
        self.settings.knowledge_index_manifest_path.mkdir(parents=True, exist_ok=True)

    def _write_processed_artifacts(
        self,
        document: KnowledgeDocumentRecord,
        chunks: list[KnowledgeChunkRecord],
    ) -> None:
        manifest_path = self.settings.knowledge_index_manifest_path / f"{document.document_id}.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "document_id": document.document_id,
                    "source_path": document.source_path,
                    "title": document.title,
                    "task_type": document.task_type,
                    "chunk_count": len(chunks),
                    "embedding_model": self.embedding_provider.model_name,
                    "vector_store_ids": [chunk.vector_store_id for chunk in chunks if chunk.vector_store_id],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        processed_path = self.settings.knowledge_processed_path / f"{document.document_id}.json"
        processed_path.write_text(
            json.dumps(
                {
                    "document_id": document.document_id,
                    "chunks": [
                        {
                            "chunk_id": chunk.chunk_id,
                            "chunk_index": chunk.chunk_index,
                            "summary": chunk.summary,
                            "content": chunk.content,
                            "metadata": chunk.metadata,
                        }
                        for chunk in chunks
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
