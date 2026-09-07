import math

import httpx
import pytest

from app.services.embeddings import (
    DeterministicEmbeddingProvider,
    EmbeddingInvalidInput,
    EmbeddingInvalidResponse,
    EmbeddingUnavailable,
    VoyageEmbeddingProvider,
    normalize_vector,
)


def test_deterministic_provider_is_stable_normalized_and_distinguishes_inputs():
    provider = DeterministicEmbeddingProvider(dimensions=32)
    first, repeated, different = provider.embed_documents(
        ["pendulum potential energy", "pendulum potential energy", "satirical social critique"]
    )
    assert first == repeated
    assert first != different
    assert math.isclose(sum(value * value for value in first), 1.0)
    assert provider.embed_query("pendulum potential energy") == first


def test_embedding_validation_rejects_empty_wrong_dimension_and_nonfinite():
    provider = DeterministicEmbeddingProvider(dimensions=8)
    with pytest.raises(EmbeddingInvalidInput):
        provider.embed_query("  ")
    with pytest.raises(EmbeddingInvalidResponse):
        normalize_vector([1.0], dimensions=2)
    with pytest.raises(EmbeddingInvalidResponse):
        normalize_vector([float("nan"), 1.0], dimensions=2)
    with pytest.raises(EmbeddingInvalidResponse):
        normalize_vector([0.0, 0.0], dimensions=2)


def test_voyage_provider_never_silently_runs_without_credentials(monkeypatch):
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    with pytest.raises(EmbeddingUnavailable):
        VoyageEmbeddingProvider()


def test_voyage_provider_uses_bounded_rate_limit_backoff(monkeypatch):
    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
    monkeypatch.setenv("RAG_EMBEDDING_RATE_LIMIT_BACKOFF_SECONDS", "20.5")
    sleeps = []
    responses = [
        httpx.Response(429, request=httpx.Request("POST", "https://api.voyageai.com/v1/embeddings")),
        httpx.Response(200, request=httpx.Request("POST", "https://api.voyageai.com/v1/embeddings"), json={
            "data": [{"index": 0, "embedding": [1.0] + [0.0] * 511}],
        }),
    ]
    monkeypatch.setattr("app.services.embeddings.httpx.post", lambda *args, **kwargs: responses.pop(0))
    monkeypatch.setattr("app.services.embeddings.time.sleep", sleeps.append)

    vector = VoyageEmbeddingProvider().embed_query("bounded CC0 query")

    assert vector[0] == 1.0
    assert sleeps == [20.5]


def test_voyage_provider_stops_after_configured_rate_limit_retries(monkeypatch):
    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
    monkeypatch.setenv("RAG_EMBEDDING_MAX_RETRIES", "1")
    monkeypatch.setenv("RAG_EMBEDDING_RATE_LIMIT_BACKOFF_SECONDS", "7")
    sleeps = []

    def rate_limited(*args, **kwargs):
        return httpx.Response(429, request=httpx.Request("POST", "https://api.voyageai.com/v1/embeddings"))

    monkeypatch.setattr("app.services.embeddings.httpx.post", rate_limited)
    monkeypatch.setattr("app.services.embeddings.time.sleep", sleeps.append)

    with pytest.raises(EmbeddingUnavailable):
        VoyageEmbeddingProvider().embed_query("bounded CC0 query")
    assert sleeps == [7.0]
