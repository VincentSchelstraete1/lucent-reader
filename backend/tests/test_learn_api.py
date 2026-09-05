import json

from app.services.learn_tutor import set_tutor_provider


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
    assert wrong["step"] is not None, (wrong["status"], wrong["objectiveIndex"], wrong["stepIndex"], wrong["report"])
    assert wrong["step"]["id"] != next_step["step"]["id"]
    assert wrong["action"]["type"] in {"give_example", "decrease_difficulty", "clarify_definition", "give_analogy"}

    remediation = client.post(f"/learn-sessions/{session['id']}/responses", json={"response": "the source-grounded relationship"}).json()
    assert remediation["status"] in {"active", "completed"}


def test_learn_session_is_owned_and_resumable(client):
    document = _document_with_note(client)
    first = client.post(f"/documents/{document['id']}/learn-sessions", json={"goal": "understand", "familiarity": "reviewing"}).json()
    resumed = client.post(f"/documents/{document['id']}/learn-sessions", json={"goal": "understand", "familiarity": "reviewing"}).json()
    assert resumed["id"] == first["id"]
    assert resumed["goal"] == "understand"
    active = client.get(f"/documents/{document['id']}/learn-sessions/active")
    assert active.status_code == 200
    assert active.json()["id"] == first["id"]


def test_ask_lucent_model_fake_provider_returns_grounded_answer(client):
    document = _document_with_note(client)
    session = client.post(f"/documents/{document['id']}/learn-sessions", json={"goal": "understand", "familiarity": "new"}).json()

    def fake_provider(_prompt, tool_name, _schema, **_kwargs):
        assert tool_name == "ask_lucent"
        return {"answer": "The saved material identifies the core idea.", "toolCalls": [{"tool": "request_explanation", "arguments": {}}], "sourceSectionIds": ["s1"], "sourceBlockIds": ["b1"]}

    set_tutor_provider(fake_provider)
    try:
        response = client.post(f"/learn-sessions/{session['id']}/ask", json={"message": "Why does this idea matter?"})
        assert response.status_code == 200
        assert response.json()["answer"].startswith("The saved material")
        assert response.json()["scope"] != "OUT_OF_SCOPE"
    finally:
        set_tutor_provider(None)


def test_model_tutor_replans_to_a_bounded_grounded_candidate(client):
    document = _document_with_note(client)
    session = client.post(f"/documents/{document['id']}/learn-sessions", json={"goal": "solve", "familiarity": "new"}).json()
    client.post(f"/learn-sessions/{session['id']}/responses", json={})
    calls = []

    def fake_provider(_prompt, tool_name, _schema, **_kwargs):
        calls.append(tool_name)
        if tool_name == "learn_tutor_decision":
            return {"hypothesis": "The learner needs a source-specific recheck.", "diagnosis": "KNOWLEDGE_GAP", "confidence": 0.8, "pedagogicalGoal": "BUILD_INTUITION", "pedagogicalStrategy": "CONCRETE_EXAMPLE", "teachingAction": "give_example", "targetConcept": "objective-s1", "interactionType": "short_answer", "scaffoldLevel": "GUIDED", "visualAction": None, "prerequisiteBranch": None, "actions": [{"tool": "give_example", "arguments": {}}], "expectedEvidence": "The learner states the material's actual idea.", "transitionMessage": "Let’s use a concrete source example.", "nextStepId": "s1-apply-repair-2", "rationale": "A bounded alternate check is the safest next intervention."}
        raise AssertionError(f"unexpected provider call: {tool_name}")

    set_tutor_provider(fake_provider)
    try:
        response = client.post(f"/learn-sessions/{session['id']}/responses", json={"response": "unrelated"})
        assert response.status_code == 200
        payload = response.json()
        assert "learn_tutor_decision" in calls
        assert payload["step"]["id"] == "s1-apply-repair-2"
        assert payload["action"]["type"] == "give_example"
    finally:
        set_tutor_provider(None)
