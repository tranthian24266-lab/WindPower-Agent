from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
import json
from typing import Any

import httpx

from app.core.embedding_provider import EmbeddingProvider, build_embedding_provider
from app.core.knowledge_repository import KnowledgeChunkRecord, KnowledgeDocumentRecord, KnowledgeRepository
from app.core.settings import Settings


@dataclass
class VectorSearchResponse:
    status: str
    mode: str
    results: list[dict[str, Any]]
    error: str | None = None


class _RestQdrantClient:
    def __init__(self, *, url: str, api_key: str | None):
        self.base_url = url.rstrip("/")
        self.api_key = api_key
        self.timeout = 30.0
        self.client = httpx.Client(timeout=self.timeout, trust_env=False)

    @property
    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["api-key"] = self.api_key
        return headers

    def collection_exists(self, name: str) -> bool:
        response = httpx.get(
            f"{self.base_url}/collections/{name}",
            headers=self._headers,
            timeout=self.timeout,
            trust_env=False,
        )
        if response.status_code == 404:
            return False
        response.raise_for_status()
        return True

    def create_collection(self, collection_name: str, vectors_config: object) -> None:
        response = httpx.put(
            f"{self.base_url}/collections/{collection_name}",
            headers=self._headers,
            json={"vectors": vectors_config},
            timeout=self.timeout,
            trust_env=False,
        )
        response.raise_for_status()

    def delete_collection(self, collection_name: str) -> None:
        response = httpx.delete(
            f"{self.base_url}/collections/{collection_name}",
            headers=self._headers,
            timeout=self.timeout,
            trust_env=False,
        )
        if response.status_code not in {200, 202, 404}:
            response.raise_for_status()

    def get_collection(self, collection_name: str) -> dict[str, Any]:
        response = httpx.get(
            f"{self.base_url}/collections/{collection_name}",
            headers=self._headers,
            timeout=self.timeout,
            trust_env=False,
        )
        response.raise_for_status()
        payload = response.json()
        return dict(payload.get("result") or {})

    def create_payload_index(self, collection_name: str, field_name: str, field_schema: object) -> None:
        response = httpx.put(
            f"{self.base_url}/collections/{collection_name}/index",
            headers=self._headers,
            json={"field_name": field_name, "field_schema": field_schema},
            timeout=self.timeout,
            trust_env=False,
        )
        response.raise_for_status()

    def delete(self, collection_name: str, points_selector: object, wait: bool = True) -> None:
        response = httpx.post(
            f"{self.base_url}/collections/{collection_name}/points/delete",
            headers=self._headers,
            params={"wait": str(wait).lower()},
            json=points_selector,
            timeout=self.timeout,
            trust_env=False,
        )
        response.raise_for_status()

    def upsert(self, collection_name: str, points: list[object], wait: bool = True) -> None:
        payload_points = [self._normalize_point(point) for point in points]
        response = httpx.put(
            f"{self.base_url}/collections/{collection_name}/points",
            headers=self._headers,
            params={"wait": str(wait).lower()},
            json={"points": payload_points},
            timeout=self.timeout,
            trust_env=False,
        )
        response.raise_for_status()

    def search(
        self,
        *,
        collection_name: str,
        query_vector: list[float],
        limit: int,
        query_filter: object,
        with_payload: bool,
    ) -> list[dict[str, Any]]:
        response = httpx.post(
            f"{self.base_url}/collections/{collection_name}/points/search",
            headers=self._headers,
            json={
                "vector": query_vector,
                "limit": limit,
                "filter": query_filter,
                "with_payload": with_payload,
            },
            timeout=self.timeout,
            trust_env=False,
        )
        response.raise_for_status()
        payload = response.json()
        return list(payload.get("result") or [])

    def _normalize_point(self, point: object) -> dict[str, Any]:
        if isinstance(point, dict):
            return point
        return {
            "id": getattr(point, "id"),
            "vector": getattr(point, "vector"),
            "payload": getattr(point, "payload"),
        }


class VectorIndexService:
    PAYLOAD_INDEX_FIELDS = (
        "metadata.task_type",
        "metadata.component",
        "metadata.source_type",
        "metadata.model_version_id",
    )

    def __init__(
        self,
        settings: Settings,
        repository: KnowledgeRepository | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ):
        self.settings = settings
        self.repository = repository or KnowledgeRepository(settings.database_path)
        selection = build_embedding_provider(
            settings.embedding_provider_name,
            model_name=settings.embedding_model_name,
        )
        self.embedding_provider = embedding_provider or selection.provider
        self.embedding_selection = selection

    def sync_document_chunks(
        self,
        document: KnowledgeDocumentRecord,
        chunks: list[KnowledgeChunkRecord],
    ) -> dict[str, Any]:
        for chunk in chunks:
            chunk.embedding_model = self.embedding_provider.model_name
            chunk.vector_store_id = None

        if not chunks:
            return {
                "status": "skipped",
                "mode": "empty",
                "indexed_count": 0,
                "embedding_model": self.embedding_provider.model_name,
            }

        if not self._remote_enabled():
            return {
                "status": "skipped",
                "mode": "local_only",
                "indexed_count": 0,
                "embedding_model": self.embedding_provider.model_name,
            }

        client = self._create_client()
        if client is None:
            return {
                "status": "fallback",
                "mode": "local_only",
                "indexed_count": 0,
                "embedding_model": self.embedding_provider.model_name,
                "error": "qdrant_client_unavailable",
            }

        try:
            vectors = self._embed_texts([chunk.content for chunk in chunks])
            self._ensure_collection(client, len(vectors[0]))
            self._ensure_payload_indexes(client)
            self._delete_document_points(client, document.document_id)
            points = [self._build_point(chunk, vector, document) for chunk, vector in zip(chunks, vectors)]
            self._upsert_points(client, points)
            for chunk in chunks:
                chunk.vector_store_id = chunk.chunk_id
            return {
                "status": "ok",
                "mode": "qdrant_upserted",
                "indexed_count": len(chunks),
                "embedding_model": self.embedding_provider.model_name,
            }
        except Exception as exc:
            return {
                "status": "fallback",
                "mode": "local_only",
                "indexed_count": 0,
                "embedding_model": self.embedding_provider.model_name,
                "error": str(exc),
            }

    def reindex_all(self, *, force_recreate: bool | None = None) -> dict[str, Any]:
        chunks = self.repository.list_chunks(limit=None)
        chunk_records = [
            KnowledgeChunkRecord(
                chunk_id=str(item["chunk_id"]),
                document_id=str(item["document_id"]),
                chunk_index=int(item["chunk_index"]),
                content=str(item["content"]),
                summary=item.get("summary"),
                tokens_estimate=item.get("tokens_estimate"),
                embedding_model=item.get("embedding_model"),
                vector_store_id=item.get("vector_store_id"),
                keywords=list(item.get("keywords") or []),
                citations=list(item.get("citations") or []),
                metadata=dict(item.get("metadata") or {}),
                created_at=str(item["created_at"]),
            )
            for item in chunks
        ]
        documents_by_id = {item["document_id"]: item for item in self.repository.list_documents()}

        if not chunk_records:
            return self._finalize_reindex_summary(
                {
                    "status": "skipped",
                    "mode": "empty",
                    "chunk_count": 0,
                    "indexed_count": 0,
                    "embedding_model": self.embedding_provider.model_name,
                }
            )

        if not self._remote_enabled():
            return self._finalize_reindex_summary(
                {
                    "status": "skipped",
                    "mode": "local_only",
                    "chunk_count": len(chunk_records),
                    "indexed_count": 0,
                    "embedding_model": self.embedding_provider.model_name,
                }
            )

        client = self._create_client()
        if client is None:
            return self._finalize_reindex_summary(
                {
                    "status": "fallback",
                    "mode": "local_only",
                    "chunk_count": len(chunk_records),
                    "indexed_count": 0,
                    "embedding_model": self.embedding_provider.model_name,
                    "error": "qdrant_client_unavailable",
                }
            )

        try:
            vectors = self._embed_texts([chunk.content for chunk in chunk_records])
            self._ensure_collection(client, len(vectors[0]), force_recreate=force_recreate)
            self._ensure_payload_indexes(client)
            if not (force_recreate or self.settings.qdrant_recreate_collection_on_rebuild):
                for document_id in documents_by_id:
                    self._delete_document_points(client, document_id)

            points = []
            for chunk, vector in zip(chunk_records, vectors):
                document = documents_by_id.get(chunk.document_id, {})
                chunk.embedding_model = self.embedding_provider.model_name
                chunk.vector_store_id = chunk.chunk_id
                points.append(self._build_point(chunk, vector, document))
            self._upsert_points(client, points)
            self.repository.update_chunk_vector_metadata(
                [
                    {
                        "chunk_id": chunk.chunk_id,
                        "embedding_model": chunk.embedding_model,
                        "vector_store_id": chunk.vector_store_id,
                    }
                    for chunk in chunk_records
                ]
            )
            return self._finalize_reindex_summary(
                {
                    "status": "ok",
                    "mode": "qdrant_reindexed",
                    "chunk_count": len(chunk_records),
                    "indexed_count": len(chunk_records),
                    "embedding_model": self.embedding_provider.model_name,
                    "force_recreate": bool(force_recreate or self.settings.qdrant_recreate_collection_on_rebuild),
                }
            )
        except Exception as exc:
            return self._finalize_reindex_summary(
                {
                    "status": "fallback",
                    "mode": "local_only",
                    "chunk_count": len(chunk_records),
                    "indexed_count": 0,
                    "embedding_model": self.embedding_provider.model_name,
                    "error": str(exc),
                }
            )

    def search(
        self,
        *,
        query_text: str,
        filters: dict[str, Any],
        top_k: int,
    ) -> VectorSearchResponse:
        if not self._remote_enabled():
            return VectorSearchResponse(status="skipped", mode="local_only", results=[])

        client = self._create_client()
        if client is None:
            return VectorSearchResponse(
                status="fallback",
                mode="local_only",
                results=[],
                error="qdrant_client_unavailable",
            )

        try:
            query_vector = self.embedding_provider.embed_query(query_text)
            qdrant_filter = self._build_qdrant_filter(filters)
            search = getattr(client, "search", None)
            if search is None:
                raise RuntimeError("Qdrant client does not expose search().")
            raw_results = search(
                collection_name=self.settings.qdrant_collection_name,
                query_vector=query_vector,
                limit=top_k,
                query_filter=qdrant_filter,
                with_payload=True,
            )
            parsed = [self._parse_search_result(item) for item in raw_results]
            return VectorSearchResponse(status="ok", mode="qdrant_dense", results=parsed)
        except Exception as exc:
            return VectorSearchResponse(status="fallback", mode="local_only", results=[], error=str(exc))

    def get_status(self) -> dict[str, Any]:
        stats = self.repository.get_index_stats()
        status = {
            "status": "ok",
            "remote_enabled": self._remote_enabled(),
            "qdrant_enabled": self.settings.qdrant_enabled,
            "qdrant_prefer_remote": self.settings.qdrant_prefer_remote,
            "qdrant_collection_name": self.settings.qdrant_collection_name,
            "qdrant_url_configured": bool(self.settings.qdrant_url),
            "embedding_provider_requested": self.settings.embedding_provider_name,
            "embedding_provider_resolved": self.embedding_provider.provider_name,
            "embedding_model_name": self.embedding_provider.model_name,
            "embedding_fallback_used": self.embedding_selection.fallback_used,
            "embedding_warning": self.embedding_selection.warning,
            "remote_ping_ok": False,
            "payload_indexes": [],
            **stats,
        }
        status.update(self._load_last_reindex_summary())

        if not self._remote_enabled():
            status["remote_available"] = False
            status["remote_error"] = "qdrant_disabled_or_unconfigured"
            return status

        client = self._create_client()
        if client is None:
            status["remote_available"] = False
            status["remote_error"] = "qdrant_client_unavailable"
            return status

        try:
            exists = self._collection_exists(client)
            status["remote_available"] = True
            status["remote_ping_ok"] = True
            status["remote_collection_exists"] = exists
            if exists:
                info = self._get_collection_info(client)
                if info:
                    status["remote_collection"] = info
                    status["payload_indexes"] = self._extract_payload_indexes(info)
        except Exception as exc:
            status["remote_available"] = False
            status["remote_error"] = str(exc)
        return status

    def _remote_enabled(self) -> bool:
        return bool(self.settings.qdrant_enabled and self.settings.qdrant_url)

    def _create_client(self) -> Any | None:
        try:
            from qdrant_client import QdrantClient
        except Exception:
            if not self.settings.qdrant_url:
                return None
            return _RestQdrantClient(url=self.settings.qdrant_url, api_key=self.settings.qdrant_api_key)
        return QdrantClient(url=self.settings.qdrant_url, api_key=self.settings.qdrant_api_key)

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        batch_size = max(1, self.settings.embedding_batch_size)
        vectors: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            vectors.extend(self.embedding_provider.embed_documents(texts[start : start + batch_size]))
        return vectors

    def _ensure_collection(self, client: Any, vector_size: int, *, force_recreate: bool | None = None) -> None:
        recreate = bool(force_recreate or self.settings.qdrant_recreate_collection_on_rebuild)
        collection_exists = self._collection_exists(client)
        if recreate and collection_exists:
            delete_collection = getattr(client, "delete_collection", None)
            if delete_collection is not None:
                delete_collection(self.settings.qdrant_collection_name)
                collection_exists = False

        if collection_exists:
            return

        vectors_config = self._build_vectors_config(vector_size)
        create_collection = getattr(client, "create_collection", None)
        recreate_collection = getattr(client, "recreate_collection", None)
        if recreate_collection is not None and recreate:
            recreate_collection(collection_name=self.settings.qdrant_collection_name, vectors_config=vectors_config)
            return
        if create_collection is None:
            raise RuntimeError("Qdrant client does not expose create_collection().")
        create_collection(collection_name=self.settings.qdrant_collection_name, vectors_config=vectors_config)

    def _collection_exists(self, client: Any) -> bool:
        collection_exists = getattr(client, "collection_exists", None)
        if collection_exists is not None:
            return bool(collection_exists(self.settings.qdrant_collection_name))
        get_collection = getattr(client, "get_collection", None)
        if get_collection is None:
            return False
        try:
            get_collection(self.settings.qdrant_collection_name)
            return True
        except Exception:
            return False

    def _get_collection_info(self, client: Any) -> dict[str, Any] | None:
        get_collection = getattr(client, "get_collection", None)
        if get_collection is None:
            return None
        info = get_collection(self.settings.qdrant_collection_name)
        if isinstance(info, dict):
            return info
        if hasattr(info, "dict"):
            return info.dict()
        if hasattr(info, "model_dump"):
            return info.model_dump()
        return {"raw": str(info)}

    def _ensure_payload_indexes(self, client: Any) -> None:
        create_payload_index = getattr(client, "create_payload_index", None)
        if create_payload_index is None:
            return

        field_schema = self._build_payload_field_schema()
        for field_name in self.PAYLOAD_INDEX_FIELDS:
            create_payload_index(
                collection_name=self.settings.qdrant_collection_name,
                field_name=field_name,
                field_schema=field_schema,
            )

    def _delete_document_points(self, client: Any, document_id: str) -> None:
        delete = getattr(client, "delete", None)
        if delete is None:
            return
        points_selector = self._build_document_selector(document_id)
        delete(collection_name=self.settings.qdrant_collection_name, points_selector=points_selector, wait=True)

    def _upsert_points(self, client: Any, points: list[Any]) -> None:
        if not points:
            return
        upsert = getattr(client, "upsert", None)
        if upsert is None:
            raise RuntimeError("Qdrant client does not expose upsert().")
        upsert(collection_name=self.settings.qdrant_collection_name, points=points, wait=True)

    def _build_vectors_config(self, vector_size: int) -> Any:
        try:
            from qdrant_client.http.models import Distance, VectorParams
        except Exception:
            return {"size": vector_size, "distance": "Cosine"}
        return VectorParams(size=vector_size, distance=Distance.COSINE)

    def _build_payload_field_schema(self) -> Any:
        try:
            from qdrant_client.http.models import PayloadSchemaType
        except Exception:
            return "keyword"
        return PayloadSchemaType.KEYWORD

    def _build_qdrant_filter(self, filters: dict[str, Any]) -> Any:
        cleaned = {key: value for key, value in filters.items() if value}
        if not cleaned:
            return None
        try:
            from qdrant_client.http.models import FieldCondition, Filter, MatchValue
        except Exception:
            return {
                "must": [
                    {"key": f"metadata.{key}", "match": {"value": value}}
                    for key, value in cleaned.items()
                ]
            }
        return Filter(
            must=[
                FieldCondition(key=f"metadata.{key}", match=MatchValue(value=value))
                for key, value in cleaned.items()
            ]
        )

    def _build_document_selector(self, document_id: str) -> Any:
        try:
            from qdrant_client.http.models import FieldCondition, Filter, FilterSelector, MatchValue
        except Exception:
            return {
                "filter": {
                    "must": [
                        {"key": "document_id", "match": {"value": document_id}},
                    ]
                }
            }
        return FilterSelector(
            filter=Filter(
                must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
            )
        )

    def _build_point(self, chunk: KnowledgeChunkRecord, vector: list[float], document: KnowledgeDocumentRecord | dict[str, Any]) -> Any:
        payload = {
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "summary": chunk.summary,
            "keywords": chunk.keywords,
            "citations": chunk.citations,
            "metadata": {
                **dict(chunk.metadata),
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "embedding_model": self.embedding_provider.model_name,
            },
        }
        if isinstance(document, KnowledgeDocumentRecord):
            payload.update(
                {
                    "title": document.title,
                    "source_path": document.source_path,
                    "source_type": document.source_type,
                    "task_type": document.task_type,
                    "component": document.component,
                    "model_family_id": document.model_family_id,
                    "model_version_id": document.model_version_id,
                }
            )
        else:
            payload.update(
                {
                    "title": document.get("title"),
                    "source_path": document.get("source_path"),
                    "source_type": document.get("source_type"),
                    "task_type": document.get("task_type"),
                    "component": document.get("component"),
                    "model_family_id": document.get("model_family_id"),
                    "model_version_id": document.get("model_version_id"),
                }
            )

        try:
            from qdrant_client.http.models import PointStruct
        except Exception:
            return {"id": chunk.chunk_id, "vector": vector, "payload": payload}
        return PointStruct(id=chunk.chunk_id, vector=vector, payload=payload)

    def _parse_search_result(self, item: Any) -> dict[str, Any]:
        payload = item.payload if hasattr(item, "payload") else item.get("payload", {})
        score = item.score if hasattr(item, "score") else item.get("score", 0.0)
        payload = dict(payload or {})
        metadata = dict(payload.get("metadata") or {})
        return {
            "chunk_id": str(payload.get("chunk_id") or getattr(item, "id", "")),
            "document_id": str(payload.get("document_id") or metadata.get("document_id") or ""),
            "chunk_index": int(payload.get("chunk_index") or metadata.get("chunk_index") or 0),
            "content": str(payload.get("content") or ""),
            "summary": payload.get("summary"),
            "title": str(payload.get("title") or metadata.get("title") or ""),
            "source_path": str(payload.get("source_path") or metadata.get("source_path") or ""),
            "source_type": str(payload.get("source_type") or metadata.get("source_type") or ""),
            "task_type": payload.get("task_type") or metadata.get("task_type"),
            "component": payload.get("component") or metadata.get("component"),
            "score": float(score),
            "metadata": metadata,
        }

    def _extract_payload_indexes(self, info: dict[str, Any]) -> list[str]:
        payload_schema = info.get("payload_schema") or {}
        if isinstance(payload_schema, dict):
            return sorted(str(key) for key in payload_schema.keys())
        return []

    def _finalize_reindex_summary(self, summary: dict[str, Any]) -> dict[str, Any]:
        manifest = {
            "last_reindex_at": datetime.now(timezone.utc).isoformat(),
            "last_reindex_status": summary.get("status"),
        }
        self.settings.knowledge_index_manifest_path.mkdir(parents=True, exist_ok=True)
        (self.settings.knowledge_index_manifest_path / "last_reindex.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return summary

    def _load_last_reindex_summary(self) -> dict[str, Any]:
        manifest_path = self.settings.knowledge_index_manifest_path / "last_reindex.json"
        if not manifest_path.exists():
            return {
                "last_reindex_at": None,
                "last_reindex_status": None,
            }
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {
                "last_reindex_at": None,
                "last_reindex_status": "invalid_manifest",
            }
        return {
            "last_reindex_at": payload.get("last_reindex_at"),
            "last_reindex_status": payload.get("last_reindex_status"),
        }
