from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import logging
import math
import os
import re
import time
from typing import Protocol, Sequence

import httpx


logger = logging.getLogger(__name__)


class EmbeddingError(RuntimeError):
    code = "embedding_error"


class EmbeddingUnavailable(EmbeddingError):
    code = "embedding_unavailable"


class EmbeddingInvalidInput(EmbeddingError):
    code = "embedding_invalid_input"


class EmbeddingInvalidResponse(EmbeddingError):
    code = "embedding_invalid_response"


@dataclass(frozen=True)
class EmbeddingMetadata:
    provider: str
    model: str
    dimensions: int


class EmbeddingProvider(Protocol):
    metadata: EmbeddingMetadata

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def normalize_vector(vector: Sequence[float], *, dimensions: int) -> list[float]:
    if len(vector) != dimensions:
        raise EmbeddingInvalidResponse("Embedding dimensions do not match the configured model")
    values = [float(item) for item in vector]
    if not all(math.isfinite(item) for item in values):
        raise EmbeddingInvalidResponse("Embedding contains a non-finite value")
    norm = math.sqrt(sum(item * item for item in values))
    if norm <= 0:
        raise EmbeddingInvalidResponse("Embedding has zero magnitude")
    return [item / norm for item in values]


def validate_inputs(texts: Sequence[str]) -> list[str]:
    cleaned = [str(text).strip() for text in texts]
    if not cleaned or any(not text for text in cleaned):
        raise EmbeddingInvalidInput("Embedding input must contain non-empty text")
    if any(len(text.encode("utf-8")) > 6000 for text in cleaned):
        raise EmbeddingInvalidInput("Embedding input exceeds the bounded source context")
    return cleaned


class VoyageEmbeddingProvider:
    def __init__(self) -> None:
        api_key = os.getenv("VOYAGE_API_KEY", "").strip()
        if not api_key:
            raise EmbeddingUnavailable("Voyage embeddings are not configured")
        self._api_key = api_key
        try:
            self._timeout = float(os.getenv("RAG_EMBEDDING_TIMEOUT_SECONDS", "20"))
            dimensions = int(os.getenv("RAG_EMBEDDING_DIMENSIONS", "512"))
            self._max_retries = int(os.getenv("RAG_EMBEDDING_MAX_RETRIES", "2"))
            self._retry_backoff = float(os.getenv("RAG_EMBEDDING_RETRY_BACKOFF_SECONDS", "0.25"))
            self._rate_limit_backoff = float(os.getenv("RAG_EMBEDDING_RATE_LIMIT_BACKOFF_SECONDS", "1"))
        except ValueError as exc:
            raise EmbeddingUnavailable("Embedding provider configuration is invalid") from exc
        if (
            self._timeout <= 0
            or dimensions <= 0
            or self._max_retries < 0
            or self._retry_backoff < 0
            or not 0 < self._rate_limit_backoff <= 60
        ):
            raise EmbeddingUnavailable("Embedding provider configuration is invalid")
        self.metadata = EmbeddingMetadata("voyage", os.getenv("RAG_EMBEDDING_MODEL", "voyage-3-lite"), dimensions)

    def _embed(self, texts: Sequence[str], *, input_type: str) -> list[list[float]]:
        started = time.perf_counter()
        values = validate_inputs(texts)
        body = None
        last_error: Exception | None = None
        attempts = self._max_retries + 1
        for attempt in range(attempts):
            retry_delay = self._retry_backoff * (2**attempt)
            try:
                response = httpx.post(
                    "https://api.voyageai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={"input": values, "model": self.metadata.model, "input_type": input_type},
                    timeout=self._timeout,
                )
                response.raise_for_status()
                body = response.json()
                break
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in {400, 401, 403, 404}:
                    logger.warning(
                        "provider_operation_complete provider=voyage operation=embed_%s outcome=rejected exception_type=%s duration_ms=%.1f attempts=%s item_count=%s model=%s http_status=%s",
                        input_type,
                        type(exc).__name__,
                        (time.perf_counter() - started) * 1000,
                        attempt + 1,
                        len(values),
                        self.metadata.model,
                        exc.response.status_code,
                    )
                    raise EmbeddingUnavailable("Embedding provider configuration was rejected") from exc
                last_error = exc
                if exc.response.status_code == 429:
                    retry_after = _retry_after_seconds(exc.response.headers.get("retry-after", ""))
                    retry_delay = self._rate_limit_backoff if retry_after is None else retry_after
            except (TypeError, ValueError) as exc:
                logger.warning(
                    "provider_operation_complete provider=voyage operation=embed_%s outcome=invalid exception_type=%s duration_ms=%.1f attempts=%s item_count=%s model=%s",
                    input_type,
                    type(exc).__name__,
                    (time.perf_counter() - started) * 1000,
                    attempt + 1,
                    len(values),
                    self.metadata.model,
                )
                raise EmbeddingInvalidResponse("Embedding provider returned malformed data") from exc
            if attempt < attempts - 1:
                time.sleep(retry_delay)
        if body is None:
            logger.warning(
                "provider_operation_complete provider=voyage operation=embed_%s outcome=error exception_type=%s duration_ms=%.1f attempts=%s item_count=%s model=%s",
                input_type,
                type(last_error).__name__ if last_error is not None else "EmbeddingUnavailable",
                (time.perf_counter() - started) * 1000,
                attempts,
                len(values),
                self.metadata.model,
            )
            raise EmbeddingUnavailable("Embedding provider is temporarily unavailable") from last_error

        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, list) or len(data) != len(values):
            logger.warning(
                "provider_operation_complete provider=voyage operation=embed_%s outcome=invalid exception_type=%s duration_ms=%.1f attempts=%s item_count=%s model=%s",
                input_type,
                "EmbeddingInvalidResponse",
                (time.perf_counter() - started) * 1000,
                attempts,
                len(values),
                self.metadata.model,
            )
            raise EmbeddingInvalidResponse("Embedding provider returned an unexpected item count")
        try:
            ordered = sorted(data, key=lambda item: int(item.get("index", 0)))
            vectors = [normalize_vector(item["embedding"], dimensions=self.metadata.dimensions) for item in ordered]
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "provider_operation_complete provider=voyage operation=embed_%s outcome=invalid exception_type=%s duration_ms=%.1f attempts=%s item_count=%s model=%s",
                input_type,
                type(exc).__name__,
                (time.perf_counter() - started) * 1000,
                attempts,
                len(values),
                self.metadata.model,
            )
            raise EmbeddingInvalidResponse("Embedding provider returned malformed vectors") from exc
        logger.info(
            "provider_operation_complete provider=voyage operation=embed_%s outcome=success exception_type=none duration_ms=%.1f attempts=%s item_count=%s model=%s",
            input_type,
            (time.perf_counter() - started) * 1000,
            attempt + 1,
            len(values),
            self.metadata.model,
        )
        return vectors

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embed(texts, input_type="document")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], input_type="query")[0]


def _retry_after_seconds(value: str, *, now: datetime | None = None) -> float | None:
    """Parse the standard Retry-After seconds or HTTP-date form, bounded to 60s."""
    candidate = str(value or "").strip()
    if not candidate:
        return None
    try:
        return min(60.0, max(0.0, float(candidate)))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(candidate)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            current = now or datetime.now(timezone.utc)
            return min(60.0, max(0.0, (retry_at - current).total_seconds()))
        except (TypeError, ValueError, OverflowError):
            return None


class DeterministicEmbeddingProvider:
    """Stable offline provider for lifecycle/integration tests, not semantic evaluation."""

    def __init__(self, dimensions: int = 512) -> None:
        self.metadata = EmbeddingMetadata("fake", "deterministic-hash-v1", dimensions)

    def _vector(self, text: str) -> list[float]:
        [cleaned] = validate_inputs([text])
        vector = [0.0] * self.metadata.dimensions
        for token in re.findall(r"[a-z0-9]+", cleaned.casefold()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.metadata.dimensions
            vector[index] += -1.0 if digest[4] & 1 else 1.0
        return normalize_vector(vector, dimensions=self.metadata.dimensions)

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(text) for text in validate_inputs(texts)]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


_PROVIDER: EmbeddingProvider | None = None


def set_embedding_provider(provider: EmbeddingProvider | None) -> None:
    global _PROVIDER
    _PROVIDER = provider


def get_embedding_provider() -> EmbeddingProvider:
    if _PROVIDER is not None:
        return _PROVIDER
    return VoyageEmbeddingProvider()
