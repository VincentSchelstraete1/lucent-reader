import json


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
