from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import hashlib
import math
import re


class EmbeddingProviderError(RuntimeError):
    """Raised when embeddings cannot be produced safely."""


class EmbeddingProvider(ABC):
    provider_name: str
    model_name: str

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding per input text."""

    def embed_query(self, text: str) -> list[float]:
        embeddings = self.embed_documents([text])
        if not embeddings:
            raise EmbeddingProviderError("Embedding provider returned no query embedding.")
        return embeddings[0]


class LocalNgramEmbeddingProvider(EmbeddingProvider):
    """A deterministic local character n-gram embedding provider for default retrieval."""

    def __init__(
        self,
        dimensions: int = 96,
        provider_name: str = "local_ngram",
        model_name: str = "char-ngram-v1",
        ngram_min: int = 3,
        ngram_max: int = 5,
    ):
        self.dimensions = max(dimensions, 32)
        self.provider_name = provider_name
        self.model_name = model_name
        self.ngram_min = max(1, ngram_min)
        self.ngram_max = max(self.ngram_min, ngram_max)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_text(text) for text in texts]

    def _embed_text(self, text: str) -> list[float]:
        buckets = [0.0] * self.dimensions
        normalized = self._normalize(text)
        grams = self._collect_ngrams(normalized)
        if not grams:
            return buckets

        for gram in grams:
            digest = hashlib.sha256(gram.encode("utf-8")).digest()
            bucket_index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + (len(gram) - self.ngram_min) * 0.15
            buckets[bucket_index] += sign * weight

        norm = math.sqrt(sum(value * value for value in buckets))
        if norm == 0:
            return buckets
        return [value / norm for value in buckets]

    def _normalize(self, text: str) -> str:
        cleaned = text.replace("\r", " ").replace("\n", " ").lower()
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _collect_ngrams(self, text: str) -> list[str]:
        if not text:
            return []
        padded = f" {text} "
        grams: list[str] = []
        for size in range(self.ngram_min, self.ngram_max + 1):
            if len(padded) < size:
                continue
            for index in range(len(padded) - size + 1):
                gram = padded[index : index + size]
                if gram.strip():
                    grams.append(gram)
        if grams:
            return grams
        return [token for token in text.split(" ") if token]


class HashEmbeddingProvider(EmbeddingProvider):
    """A deterministic local embedding fallback for small knowledge bases and tests."""

    def __init__(self, dimensions: int = 24, provider_name: str = "local_hash", model_name: str = "hash-v1"):
        self.dimensions = max(dimensions, 8)
        self.provider_name = provider_name
        self.model_name = model_name

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_text(text) for text in texts]

    def _embed_text(self, text: str) -> list[float]:
        buckets = [0.0] * self.dimensions
        tokens = [token for token in self._tokenize(text) if token]
        if not tokens:
            return buckets

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for index in range(self.dimensions):
                buckets[index] += digest[index % len(digest)] / 255.0

        norm = math.sqrt(sum(value * value for value in buckets))
        if norm == 0:
            return buckets
        return [value / norm for value in buckets]

    def _tokenize(self, text: str) -> list[str]:
        cleaned = text.replace("\r", " ").replace("\n", " ").lower()
        return [token.strip(".,:;!?()[]{}<>`'\"") for token in cleaned.split()]


@dataclass
class EmbeddingProviderSelection:
    provider: EmbeddingProvider
    requested_name: str
    resolved_name: str
    fallback_used: bool
    warning: str | None = None


def build_embedding_provider(
    provider_name: str | None,
    *,
    model_name: str | None = None,
) -> EmbeddingProviderSelection:
    requested = (provider_name or "local_ngram").strip().lower()

    if requested in {"local_ngram", "ngram", "char_ngram"}:
        resolved_model = model_name or "char-ngram-v1"
        provider = LocalNgramEmbeddingProvider(model_name=resolved_model)
        return EmbeddingProviderSelection(
            provider=provider,
            requested_name=requested,
            resolved_name=provider.provider_name,
            fallback_used=False,
        )

    if requested in {"local_hash", "hash"}:
        resolved_model = model_name or "hash-v1"
        provider = HashEmbeddingProvider(model_name=resolved_model)
        return EmbeddingProviderSelection(
            provider=provider,
            requested_name=requested,
            resolved_name=provider.provider_name,
            fallback_used=False,
        )

    fallback_provider = HashEmbeddingProvider(model_name=model_name or "hash-v1")
    return EmbeddingProviderSelection(
        provider=fallback_provider,
        requested_name=requested,
        resolved_name=fallback_provider.provider_name,
        fallback_used=True,
        warning=f"Unknown embedding provider '{requested}', fell back to local_hash.",
    )
