import json
import hashlib
import uuid

from app.models.learning_block import DocumentSourceIndex, PersistedLearningBlock
from app.schemas.quiz import GeneratedQuizQuestions, QuizQuestion
from app.services.embeddings import DeterministicEmbeddingProvider, set_embedding_provider
from tests.conftest import TestSessionLocal


def _make_document(client):
    source = client.post("/sources", json={"type": "website", "url": "https://example.com/quiz"}).json()
    return client.post("/documents", json={
        "source_id": source["id"], "title": "Quiz Doc", "content": "Content to quiz on."
    }).json()

def test_generate_and_retrieve_quiz(client, mock_quiz):
    document = _make_document(client)
    create_response = client.post(f"/documents/{document['id']}/quizzes")
    assert create_response.status_code == 200
    quiz = create_response.json()
    assert quiz["document_id"] == document["id"]
    assert len(quiz["questions"]) == 3

    list_response = client.get(f"/documents/{document['id']}/quizzes")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    get_response = client.get(f"/quizzes/{quiz['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == quiz["id"]


def test_quiz_uses_saved_section_note_and_links_questions_for_review(client, mock_quiz):
    document = _make_document(client)
    client.post("/notes", json={
        "title": "Section note",
        "content_type": "section_note",
        "document_id": document["id"],
        "content": json.dumps({
            "filename": "lecture.pdf",
            "sectionNotes": [{
                "id": "section-cache",
                "title": "Cache behavior",
                "bigIdea": "A cache keeps frequently used data nearby.",
                "components": [{"kind": "explanation", "text": "Cache hits avoid slower memory."}],
                "keyTakeaways": ["Hits avoid slower memory."],
            }],
        }),
    })

    quiz = client.post(f"/documents/{document['id']}/quizzes").json()

    assert {question["section_id"] for question in quiz["questions"]} == {"section-cache"}


def test_ready_index_associates_invalid_quiz_section_from_original_source(client, monkeypatch):
    document = _make_document(client)
    generation = uuid.uuid4()
    source_text = "A cache hit serves nearby data and avoids the latency of accessing slower main memory."
    provider = DeterministicEmbeddingProvider()
    vector = provider.embed_documents([source_text])[0]
    with TestSessionLocal() as db:
        db.add(DocumentSourceIndex(
            document_id=document["id"], generation_id=generation, corpus_hash="a" * 64,
            normalization_version="test", segmentation_version="test",
            embedding_input_version="learning-block-input-v1", status="READY",
            provider=provider.metadata.provider, model=provider.metadata.model,
            dimensions=provider.metadata.dimensions, block_count=1, embedded_count=1,
            coverage_warnings=[], indexed_at=None,
        ))
        db.add(PersistedLearningBlock(
            document_id=document["id"], block_id="cache-source", generation_id=generation,
            ordinal=0, block_type="paragraph", title="Cache behavior", text=source_text,
            character_count=len(source_text), token_count=None, heading_ancestry=[],
            normalized_block_ids=["normalized-cache"], section_ids=["section-cache"],
            source={"page_start": 2, "page_end": 2}, segmentation={}, attachments=[],
            content_hash=hashlib.sha256(source_text.encode()).hexdigest(),
            embedding_input_hash=hashlib.sha256(source_text.encode()).hexdigest(), embedding=vector,
        ))
        db.commit()

    client.post("/notes", json={
        "title": "Section note", "content_type": "section_note", "document_id": document["id"],
        "content": json.dumps({
            "sourceGeneration": str(generation),
            "sectionNotes": [{"id": "section-cache", "title": "Cache behavior", "bigIdea": source_text,
                              "components": [], "keyTakeaways": [source_text]}],
        }),
    })
    monkeypatch.setattr("app.routers.quizzes.generate_quiz_questions", lambda *_args, **_kwargs: GeneratedQuizQuestions(
        questions=[QuizQuestion(
            question="Why does a cache hit reduce access time?", choices=["Nearby data", "Disk access"],
            correct_index=0, explanation="The requested data is served without slower main memory.",
            section_id="invented-section",
        )]
    ))
    set_embedding_provider(provider)
    try:
        response = client.post(f"/documents/{document['id']}/quizzes")
    finally:
        set_embedding_provider(None)

    assert response.status_code == 200
    assert response.json()["questions"][0]["section_id"] == "section-cache"

def test_quiz_attempt(client, mock_quiz):
    document = _make_document(client)
    quiz = client.post(f"/documents/{document['id']}/quizzes").json()

    response = client.post(f"/quizzes/{quiz['id']}/attempts", json={"score": 2, "total": 3})
    assert response.status_code == 200
    body = response.json()
    assert body["quiz_id"] == quiz["id"]
    assert body["score"] == 2
    assert body["total"] == 3

def test_quiz_missing_document_404(client, mock_quiz):
    assert client.post("/documents/999999/quizzes").status_code == 404

def test_quiz_attempt_missing_quiz_404(client):
    response = client.post("/quizzes/999999/attempts", json={"score": 1, "total": 1})
    assert response.status_code == 404

def test_get_missing_quiz_404(client):
    assert client.get("/quizzes/999999").status_code == 404
