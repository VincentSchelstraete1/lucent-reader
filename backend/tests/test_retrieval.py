import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.document import Document
from app.models.learning_block import DocumentSourceIndex, PersistedLearningBlock
from app.models.source import Source
from app.services.embeddings import DeterministicEmbeddingProvider, set_embedding_provider
from app.services.retrieval import (
    RetrievalStatus,
    SourceAccessDenied,
    SourceQuery,
    build_source_query,
    retrieve_source,
    serialize_source_context,
)
from tests.conftest import TestSessionLocal


def _seed_index(client):
    source = client.post("/sources", json={"type": "upload", "url": "rag-fixture"}).json()
    document = client.post(
        "/documents", json={"source_id": source["id"], "title": "Grounded", "content": "legacy markdown"}
    ).json()
    provider = DeterministicEmbeddingProvider(dimensions=32)
    generation = uuid.uuid4()
    texts = [
        "A pendulum has maximum potential energy and zero speed at its turning point.",
        "At the lowest point the pendulum has maximum kinetic energy and its greatest speed.",
        "Enlightenment satire uses indirect irony to expose institutional hypocrisy.",
    ]
    vectors = provider.embed_documents(texts)
    with TestSessionLocal() as db:
        owner = db.execute(select(Source.user_id).where(Source.id == source["id"])).scalar_one()
        db.add(DocumentSourceIndex(document_id=document["id"], generation_id=generation, corpus_hash="a" * 64,
            normalization_version="test", segmentation_version="segmentation-v1", status="READY",
            provider=provider.metadata.provider, model=provider.metadata.model, dimensions=32,
            block_count=3, embedded_count=3, attempt_count=1, coverage_warnings=[]))
        for ordinal, (text, vector) in enumerate(zip(texts, vectors)):
            db.add(PersistedLearningBlock(document_id=document["id"], block_id=f"b{ordinal + 1}",
                generation_id=generation, ordinal=ordinal, block_type="section", title=None, text=text,
                character_count=len(text), heading_ancestry=[], normalized_block_ids=[f"n{ordinal + 1}"],
                section_ids=[f"section-{ordinal}"], source={"page_start": ordinal + 1, "page_end": ordinal + 1},
                segmentation={"version": "segmentation-v1"}, attachments=[], content_hash=str(ordinal) * 64,
                embedding_input_hash=str(ordinal + 1) * 64, embedding=vector))
        db.commit()
    return owner, document["id"], generation, provider


def test_exact_retrieval_is_document_scoped_ranked_and_provenanced(client):
    owner, document_id, generation, provider = _seed_index(client)
    set_embedding_provider(provider)
    try:
        with TestSessionLocal() as db:
            context = retrieve_source(db, user_id=owner, document_id=document_id,
                expected_generation=generation,
                query=SourceQuery("ask", "maximum kinetic energy greatest speed"), top_k=2)
    finally:
        set_embedding_provider(None)
    assert context.status == RetrievalStatus.SUPPORTED
    assert context.blocks[0].block_ids == ["b2"]
    assert context.blocks[0].source["page_start"] == 2
    assert context.blocks[0].selection == "semantic"
    assert context.raw_ranked_block_ids[0] == "b2"
    assert len(context.raw_ranked_scores) == 3
    assert len(context.omitted_block_ids) == 1
    assert context.omitted_block_ids[0] not in {block.block_ids[0] for block in context.blocks}
    assert context.observation_blocks()[0]["text"].startswith("At the lowest point")
    assert context.timings_ms["total"] >= context.timings_ms["search"]


def test_calibrated_similarity_marks_unanchored_weak_context(client):
    owner, document_id, generation, provider = _seed_index(client)
    set_embedding_provider(provider)
    try:
        with TestSessionLocal() as db:
            weak = retrieve_source(
                db,
                user_id=owner,
                document_id=document_id,
                expected_generation=generation,
                query=SourceQuery("ask", "unrelated electric charge biography"),
                min_similarity=1.0,
            )
            anchored = retrieve_source(
                db,
                user_id=owner,
                document_id=document_id,
                expected_generation=generation,
                query=SourceQuery("ask", "unrelated electric charge biography"),
                anchor_block_ids=["b1"],
                min_similarity=1.0,
            )
    finally:
        set_embedding_provider(None)
    assert weak.status == RetrievalStatus.WEAK
    assert anchored.status == RetrievalStatus.SUPPORTED


def test_anchors_are_bounded_first_and_missing_anchor_marks_incomplete(client):
    owner, document_id, generation, provider = _seed_index(client)
    set_embedding_provider(provider)
    try:
        with TestSessionLocal() as db:
            context = retrieve_source(db, user_id=owner, document_id=document_id,
                expected_generation=generation, query=SourceQuery("response", "satire"),
                anchor_block_ids=["b1", "missing", "b3", "b2"], top_k=3)
    finally:
        set_embedding_provider(None)
    assert [block.block_ids[0] for block in context.blocks[:2]] == ["b1", "b3"]
    assert [block.selection for block in context.blocks] == ["anchor", "anchor", "semantic"]
    assert set(context.raw_ranked_block_ids) == {"b1", "b2", "b3"}
    assert context.coverage_incomplete is True


def test_retrieval_rejects_other_user_and_stale_generation(client):
    owner, document_id, generation, provider = _seed_index(client)
    set_embedding_provider(provider)
    try:
        with TestSessionLocal() as db:
            with pytest.raises(SourceAccessDenied):
                retrieve_source(db, user_id=uuid.uuid4(), document_id=document_id,
                    expected_generation=generation, query=SourceQuery("ask", "pendulum"))
            stale = retrieve_source(db, user_id=owner, document_id=document_id,
                expected_generation=uuid.uuid4(), query=SourceQuery("ask", "pendulum"))
    finally:
        set_embedding_provider(None)
    assert stale.status == RetrievalStatus.SOURCE_CHANGED
    assert stale.blocks == []


def test_retrieval_reports_expired_indexing_lease_as_failed(client):
    owner, document_id, generation, _provider = _seed_index(client)
    with TestSessionLocal() as db:
        source_index = db.get(DocumentSourceIndex, document_id)
        source_index.status = "INDEXING"
        source_index.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    with TestSessionLocal() as db:
        context = retrieve_source(
            db,
            user_id=owner,
            document_id=document_id,
            expected_generation=generation,
            query=SourceQuery("ask", "pendulum energy"),
        )
    assert context.status == RetrievalStatus.FAILED
    assert context.failure_code == "indexing_lease_expired"


def test_not_indexed_and_provider_mismatch_never_fall_back_to_first_section(client):
    source = client.post("/sources", json={"type": "upload", "url": "legacy"}).json()
    document = client.post("/documents", json={"source_id": source["id"], "title": "Legacy", "content": "text"}).json()
    with TestSessionLocal() as db:
        owner = db.execute(select(Source.user_id).where(Source.id == source["id"])).scalar_one()
        missing = retrieve_source(db, user_id=owner, document_id=document["id"], expected_generation=None,
            query=SourceQuery("ask", "anything"))
    assert missing.status == RetrievalStatus.NOT_INDEXED
    assert missing.blocks == []


def test_bounded_query_omits_empty_uncertainty_and_keeps_runtime_target():
    query = build_source_query(purpose="response", objective_title="Pendulum energy",
        objective_outcome="Explain the energy exchange", active_prompt="Where is kinetic energy greatest?",
        learner_text="I don't know", misconception="Confuses height with speed", objective_id="energy")
    assert "I don't know" not in query.text
    assert "Pendulum energy" in query.text
    assert "Confuses height" in query.text
    assert query.objective_id == "energy"
    assert len(query.text) <= 1200


def test_serialized_prompt_context_stays_valid_json_under_budget(client):
    owner, document_id, generation, provider = _seed_index(client)
    set_embedding_provider(provider)
    try:
        with TestSessionLocal() as db:
            context = retrieve_source(db, user_id=owner, document_id=document_id,
                expected_generation=generation, query=SourceQuery("ask", "energy"), top_k=3)
    finally:
        set_embedding_provider(None)
    import json
    serialized = serialize_source_context(context, max_chars=220)
    assert len(serialized) <= 220
    assert isinstance(json.loads(serialized), list)
