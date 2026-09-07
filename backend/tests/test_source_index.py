import uuid

from sqlalchemy import select

from app.ingestion import RawContentBlock, RawDocument, RawPage
from app.main import app
from app.models.learn import LearnSession
from app.models.learning_block import DocumentSourceIndex, PersistedLearningBlock
from app.routers.ingestion import get_document_ingestor
from app.services.embeddings import DeterministicEmbeddingProvider, set_embedding_provider
from app.services.source_index import index_document
from app.services.learn_tutor import set_tutor_provider
from tests.conftest import TestSessionLocal


class MutableIngestor:
    def __init__(self, text: str) -> None:
        self.text = text

    def ingest_pdf(self, _data: bytes, *, filename: str) -> RawDocument:
        block = RawContentBlock("page-1-block-1", 1, "text", (20, 20, 500, 80), 0, self.text)
        return RawDocument(
            source_type="pdf",
            filename=filename,
            page_count=1,
            markdown=self.text,
            pages=[RawPage(1, self.text, [block])],
            images=[],
            extraction_metadata={"page_extractor": "test"},
        )


def _upload(client, ingestor: MutableIngestor, filename: str = "grounded.pdf"):
    app.dependency_overrides[get_document_ingestor] = lambda: ingestor
    set_embedding_provider(DeterministicEmbeddingProvider())
    try:
        return client.post(
            "/ingestion/pdf",
            files={"file": (filename, b"%PDF-1.4\nfixture", "application/pdf")},
        )
    finally:
        set_embedding_provider(None)
        app.dependency_overrides.pop(get_document_ingestor, None)


def test_ingestion_persists_resolvable_learning_blocks_and_public_status(client):
    response = _upload(
        client,
        MutableIngestor("A pendulum exchanges potential and kinetic energy while its total mechanical energy remains constant."),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source_generation"]
    assert body["source_index_status"] == "PENDING"

    status = client.get(f"/documents/{body['document_id']}/source-index")
    assert status.status_code == 200
    assert status.json() == {
        "document_id": body["document_id"],
        "generation_id": body["source_generation"],
        "status": "READY",
        "block_count": 1,
        "embedded_count": 1,
        "coverage_warnings": [],
        "retryable": False,
    }
    with TestSessionLocal() as db:
        block = db.execute(
            select(PersistedLearningBlock).where(PersistedLearningBlock.document_id == body["document_id"])
        ).scalar_one()
        assert "potential and kinetic energy" in block.text
        assert block.source["page_start"] == 1
        assert block.section_ids == ["section-0"]
        assert len(block.embedding) == 512


def test_identical_upload_is_idempotent_but_changed_source_invalidates_session(client):
    ingestor = MutableIngestor(
        "Satire uses irony and exaggeration to expose institutional contradictions through indirect social critique."
    )
    first = _upload(client, ingestor).json()
    second = _upload(client, ingestor).json()
    assert second["document_id"] == first["document_id"]
    assert second["source_generation"] == first["source_generation"]

    with TestSessionLocal() as db:
        source_index = db.get(DocumentSourceIndex, first["document_id"])
        session = LearnSession(
            id=uuid.uuid4(),
            user_id=db.execute(select(LearnSession.user_id).limit(1)).scalar_one_or_none() or _owner_id(db, first["document_id"]),
            document_id=first["document_id"],
            goal="understand",
            familiarity="new",
            plan={},
            state={"runtimeVersion": 2, "sourceGeneration": str(source_index.generation_id)},
            status="active",
            plan_fingerprint="fixture",
        )
        db.add(session)
        db.commit()
        session_id = session.id

    ingestor.text = "Satirical contrast also makes audiences infer hypocrisy themselves instead of receiving a direct accusation."
    changed = _upload(client, ingestor).json()
    assert changed["source_generation"] != first["source_generation"]
    with TestSessionLocal() as db:
        session = db.get(LearnSession, session_id)
        assert session.status == "stopped"
        assert session.ended_reason == "source_updated"
        assert session.state["sourceInvalidated"] is True
        rows = db.execute(
            select(PersistedLearningBlock).where(PersistedLearningBlock.document_id == first["document_id"])
        ).scalars().all()
        assert len(rows) == 1
        assert "audiences infer hypocrisy" in rows[0].text


def _owner_id(db, document_id: int):
    from app.models.document import Document
    from app.models.source import Source

    return db.execute(
        select(Source.user_id).join(Document, Document.source_id == Source.id).where(Document.id == document_id)
    ).scalar_one()


def test_diagnostic_or_metadata_only_source_cannot_create_a_corpus(client):
    diagnostic = _upload(
        client,
        MutableIngestor("Insufficient Source Material: extraction failed and the document contains no substantive content."),
        "diagnostic.pdf",
    )
    assert diagnostic.status_code == 422
    assert diagnostic.json()["detail"]["code"] == "source_not_substantive"

    metadata = _upload(client, MutableIngestor("Title Author 2026"), "metadata.pdf")
    assert metadata.status_code == 422
    assert metadata.json()["detail"]["code"] == "source_not_substantive"


def test_index_failure_is_sanitized_and_retryable(client):
    class FailingProvider(DeterministicEmbeddingProvider):
        def embed_documents(self, texts):
            from app.services.embeddings import EmbeddingUnavailable

            raise EmbeddingUnavailable("secret provider detail")

    response = _upload(
        client,
        MutableIngestor("A force changes acceleration in proportion to mass according to Newton's second law."),
        "failure.pdf",
    ).json()
    with TestSessionLocal() as db:
        source_index = db.get(DocumentSourceIndex, response["document_id"])
        source_index.status = "PENDING"
        source_index.embedded_count = 0
        for block in source_index.blocks:
            block.embedding = None
        generation = source_index.generation_id
        db.commit()

    set_embedding_provider(FailingProvider())
    try:
        assert index_document(response["document_id"], generation) is False
    finally:
        set_embedding_provider(None)
    with TestSessionLocal() as db:
        source_index = db.get(DocumentSourceIndex, response["document_id"])
        assert source_index.status == "FAILED"
        assert source_index.failure_code == "embedding_unavailable"
        assert "secret" not in source_index.failure_code


def test_ingested_learn_response_supplies_original_source_text_to_tutor(client):
    raw_source = (
        "The oscillating-source-token marks the original evidence: at a pendulum turning point, speed is zero "
        "and gravitational potential energy is greatest."
    )
    uploaded = _upload(client, MutableIngestor(raw_source), "runtime-grounding.pdf").json()
    session_response = client.post(
        f"/documents/{uploaded['document_id']}/learn-sessions",
        json={"goal": "understand", "familiarity": "new", "restart": True},
    )
    assert session_response.status_code == 200
    session = session_response.json()
    assert session["scene"]

    prompts = []
    def tutor_provider(prompt, _tool_name, _schema, **_kwargs):
        prompts.append(prompt)
        return {}

    fake_embedding = DeterministicEmbeddingProvider()
    set_embedding_provider(fake_embedding)
    set_tutor_provider(tutor_provider)
    try:
        scene = session["scene"]
        interaction_id = scene.get("responseInteractionId")
        request = {
            "sceneId": scene["id"],
            "sceneRevision": scene["revision"],
            "interactionId": interaction_id,
            "eventType": "RESPONSE" if interaction_id else "CONTINUE",
            "response": "A deliberately incomplete explanation",
            "optionId": "not-a-valid-option",
        }
        response = client.post(f"/learn-sessions/{session['id']}/responses", json=request)
    finally:
        set_tutor_provider(None)
        set_embedding_provider(None)
    assert response.status_code == 200
    assert prompts
    assert any("oscillating-source-token" in prompt for prompt in prompts)
    assert any("SOURCE_CONTEXT_UNTRUSTED" in prompt for prompt in prompts)


def test_ingested_ask_uses_same_original_source_and_does_not_mutate_evidence(client):
    raw_source = (
        "The satire-source-token identifies the source evidence: ironic praise can expose institutional hypocrisy "
        "by making an audience infer the criticism beneath a literal statement."
    )
    uploaded = _upload(client, MutableIngestor(raw_source), "ask-grounding.pdf").json()
    session = client.post(
        f"/documents/{uploaded['document_id']}/learn-sessions",
        json={"goal": "understand", "familiarity": "new", "restart": True},
    ).json()
    before_evidence = session["conceptStates"]
    active_id = session["scene"].get("responseInteractionId")
    source_block_id = uploaded["learning_blocks"][0]["id"]
    prompts = []

    def tutor_provider(prompt, tool_name, _schema, **_kwargs):
        prompts.append((tool_name, prompt))
        if tool_name == "ask_lucent":
            return {
                "answer": "Ironic praise exposes hypocrisy by prompting the audience to infer the criticism.",
                "toolCalls": [{"tool": "request_explanation", "arguments": {}}],
                "sourceSectionIds": ["section-0"],
                "sourceBlockIds": [source_block_id],
            }
        return {}

    set_embedding_provider(DeterministicEmbeddingProvider())
    set_tutor_provider(tutor_provider)
    try:
        response = client.post(
            f"/learn-sessions/{session['id']}/ask", json={"message": "Explain this another way"}
        )
    finally:
        set_tutor_provider(None)
        set_embedding_provider(None)
    assert response.status_code == 200
    body = response.json()
    assert body["sourceBlockIds"] == [source_block_id]
    assert any(tool == "ask_lucent" and "satire-source-token" in prompt for tool, prompt in prompts)
    assert body["scene"]["responseInteractionId"] == active_id
    refreshed = client.get(f"/learn-sessions/{session['id']}").json()
    assert refreshed["conceptStates"] == before_evidence
