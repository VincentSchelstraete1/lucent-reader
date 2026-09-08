import math
from datetime import datetime, timezone

import httpx
import pytest

from app.services.embeddings import (
    DeterministicEmbeddingProvider,
    EmbeddingInvalidInput,
    EmbeddingInvalidResponse,
    EmbeddingUnavailable,
    VoyageEmbeddingProvider,
    _retry_after_seconds,
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


def test_voyage_paid_tier_defaults_use_short_bounded_retries(monkeypatch):
    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
    monkeypatch.delenv("RAG_EMBEDDING_MAX_RETRIES", raising=False)
    monkeypatch.delenv("RAG_EMBEDDING_RATE_LIMIT_BACKOFF_SECONDS", raising=False)
    provider = VoyageEmbeddingProvider()
    assert provider._max_retries == 2
    assert provider._rate_limit_backoff == 1.0


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


def test_voyage_honors_retry_after_instead_of_forcing_fallback_floor(monkeypatch):
    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
    monkeypatch.setenv("RAG_EMBEDDING_MAX_RETRIES", "1")
    monkeypatch.setenv("RAG_EMBEDDING_RATE_LIMIT_BACKOFF_SECONDS", "7")
    sleeps = []
    responses = [
        httpx.Response(429, headers={"Retry-After": "0.5"}, request=httpx.Request("POST", "https://api.voyageai.com/v1/embeddings")),
        httpx.Response(200, request=httpx.Request("POST", "https://api.voyageai.com/v1/embeddings"), json={
            "data": [{"index": 0, "embedding": [1.0] + [0.0] * 511}],
        }),
    ]
    monkeypatch.setattr("app.services.embeddings.httpx.post", lambda *args, **kwargs: responses.pop(0))
    monkeypatch.setattr("app.services.embeddings.time.sleep", sleeps.append)

    VoyageEmbeddingProvider().embed_query("bounded CC0 query")

    assert sleeps == [0.5]


def test_retry_after_supports_http_date_and_bounds_delay():
    now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    assert _retry_after_seconds("Sun, 07 Sep 2026 12:00:12 GMT", now=now) == 12
    assert _retry_after_seconds("120", now=now) == 60
    assert _retry_after_seconds("invalid", now=now) is None


def test_voyage_success_telemetry_excludes_embedding_input(monkeypatch, caplog):
    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
    response = httpx.Response(200, request=httpx.Request("POST", "https://api.voyageai.com/v1/embeddings"), json={
        "data": [{"index": 0, "embedding": [1.0] + [0.0] * 511}],
    })
    monkeypatch.setattr("app.services.embeddings.httpx.post", lambda *args, **kwargs: response)
    caplog.set_level("INFO", logger="app.services.embeddings")

    VoyageEmbeddingProvider().embed_query("SECRET CC0 QUERY")

    messages = [record.getMessage() for record in caplog.records if "provider_operation_complete" in record.getMessage()]
    assert any("provider=voyage operation=embed_query outcome=success" in message for message in messages)
    assert all("SECRET CC0 QUERY" not in message for message in messages)


def test_voyage_item_count_mismatch_emits_terminal_telemetry(monkeypatch, caplog):
    """Every terminal outcome must emit provider_operation_complete, this one included."""
    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
    response = httpx.Response(200, request=httpx.Request("POST", "https://api.voyageai.com/v1/embeddings"), json={
        "data": [],
    })
    monkeypatch.setattr("app.services.embeddings.httpx.post", lambda *args, **kwargs: response)
    caplog.set_level("INFO", logger="app.services.embeddings")

    with pytest.raises(EmbeddingInvalidResponse):
        VoyageEmbeddingProvider().embed_query("SECRET CC0 QUERY")

    messages = [record.getMessage() for record in caplog.records if "provider_operation_complete" in record.getMessage()]
    assert any("provider=voyage operation=embed_query outcome=invalid" in message for message in messages)
    assert all("SECRET CC0 QUERY" not in message for message in messages)
