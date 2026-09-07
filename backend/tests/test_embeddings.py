import math

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
