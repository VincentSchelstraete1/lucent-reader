import json


def _document_with_note(client):
    source = client.post("/sources", json={"type": "website", "url": "https://example.com/learn"}).json()
    document = client.post("/documents", json={"source_id": source["id"], "title": "Learn material", "content": "Grounded material."}).json()
    client.post("/notes", json={
        "title": "Learn note", "content_type": "section_note", "document_id": document["id"],
        "content": json.dumps({"title": "Learn material", "sectionNotes": [{
            "id": "s1", "title": "Core idea", "bigIdea": "A source-grounded idea.", "sourceBlockIds": ["b1"],
            "keyTakeaways": ["The idea matters."], "components": [],
        }]}),
    })
    return document


def test_learn_session_supports_goal_sensitive_response_and_hint_flow(client):
    document = _document_with_note(client)
    session = client.post(f"/documents/{document['id']}/learn-sessions", json={"goal": "solve", "familiarity": "new"}).json()
    assert session["status"] == "active"
    assert session["step"]["type"] == "teach"

    next_step = client.post(f"/learn-sessions/{session['id']}/responses", json={}).json()
    assert next_step["step"]["type"] == "problem"
    hint = client.post(f"/learn-sessions/{session['id']}/hints", json={}).json()
    assert hint["hintsUsed"] == 1

    wrong = client.post(f"/learn-sessions/{session['id']}/responses", json={"response": "unrelated"}).json()
    assert wrong["feedbackKind"] == "incorrect"
    assert wrong["step"]["id"] == next_step["step"]["id"]

    completed = client.post(f"/learn-sessions/{session['id']}/responses", json={"response": "The idea matters."}).json()
    assert completed["status"] == "completed"


def test_learn_session_is_owned_and_resumable(client):
    document = _document_with_note(client)
    first = client.post(f"/documents/{document['id']}/learn-sessions", json={"goal": "understand", "familiarity": "reviewing"}).json()
    resumed = client.post(f"/documents/{document['id']}/learn-sessions", json={"goal": "understand", "familiarity": "reviewing"}).json()
    assert resumed["id"] == first["id"]
    assert resumed["goal"] == "understand"
    active = client.get(f"/documents/{document['id']}/learn-sessions/active")
    assert active.status_code == 200
    assert active.json()["id"] == first["id"]
