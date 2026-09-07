import json
import re
from types import SimpleNamespace

from app.services.learn_tutor import set_tutor_provider
from app.services.learn_engine import build_remediation_step
from app.schemas.learn import MultipleChoiceStep


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


def test_remediation_step_preserves_source_context_without_mutating_plan():
    failed = MultipleChoiceStep(
        id="check-energy", type="multiple_choice", title="Energy conversion",
        prompt="Where is speed greatest?", options=[{"id": "a", "label": "At the bottom"}, {"id": "b", "label": "At the top"}], answerId="a",
        sourceSectionIds=["s1"], sourceBlockIds=["b1"],
    )
    objective = {"id": "energy", "title": "Pendulum energy", "outcome": "Potential energy becomes kinetic energy as the pendulum falls.", "bottleneck": "Connect speed to kinetic energy.", "steps": []}
    repair = build_remediation_step(objective, failed, "repair-1")
    assert repair.source_block_ids == ["b1"]
    # Pure content generation: the objective/plan is never mutated.
    assert objective["steps"] == []


def test_learn_session_supports_goal_sensitive_response_and_hint_flow(client):
    document = _document_with_note(client)
    session = client.post(f"/documents/{document['id']}/learn-sessions", json={"goal": "solve", "familiarity": "new"}).json()
    assert session["status"] == "active"
    assert session["scene"] is not None
    assert any(block["kind"] == "explanation" for block in session["scene"]["blocks"])

    next_step = client.post(f"/learn-sessions/{session['id']}/responses", json={}).json()
    # Continue acknowledges a scene that already has an active response; it
    # must not rewind or manufacture a second legacy step.
    assert next_step["scene"]["revision"] >= session["scene"]["revision"]
    active_id = next_step["scene"].get("responseInteractionId")
    if active_id:
        hint = client.post(f"/learn-sessions/{session['id']}/hints", json={"interactionId": active_id}).json()
        assert hint["hintsUsed"] == 1

    wrong = client.post(f"/learn-sessions/{session['id']}/responses", json={"interactionId": active_id, "eventType": "RESPONSE", "response": "unrelated"}).json()
    if active_id:
        assert wrong["feedbackKind"] == "incorrect"
        assert wrong["scene"] is not None
        assert wrong["scene"]["revision"] > next_step["scene"]["revision"]
    # The authoritative scene carries the pedagogical change; the legacy
    # action envelope is intentionally empty during scene-only runtime.
    assert wrong["scene"] is not None

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

def test_ask_example_replaces_provider_retrieval_narration_with_grounded_content(client):
    source = client.post("/sources", json={"type": "website", "url": "https://example.com/satire"}).json()
    document = client.post("/documents", json={"source_id": source["id"], "title": "Satire material", "content": "A source-grounded comparison."}).json()
    note = {"title": "Satire", "sectionNotes": [{"id": "satire", "title": "Satire as critique", "bigIdea": "Satire exposes hypocrisy through exaggerated sincere claims.", "sourceBlockIds": ["b1"], "components": [{"kind": "comparison", "items": [{"id": "surface", "name": "surface statement", "values": {"role": "sounds sincere"}}, {"id": "critique", "name": "underlying critique", "values": {"role": "exposes hypocrisy"}}]}]}]}
    client.post("/notes", json={"title": "Satire", "content_type": "section_note", "document_id": document["id"], "content": json.dumps(note)})
    session = client.post(f"/documents/{document['id']}/learn-sessions", json={"goal": "understand", "familiarity": "new"}).json()
    def fake_provider(_prompt, tool_name, _schema, **_kwargs):
        if tool_name == "ask_lucent":
            return {"answer": "I'd be happy to help with an example. Let me retrieve the available sources.", "toolCalls": [{"tool": "request_example", "arguments": {}}], "sourceSectionIds": ["satire"], "sourceBlockIds": ["b1"]}
        return None
    set_tutor_provider(fake_provider)
    try:
        response = client.post(f"/learn-sessions/{session['id']}/ask", json={"message": "Give me an example"})
        assert response.status_code == 200
        answer = response.json()["answer"]
        assert "surface statement" in answer and "underlying critique" in answer
        assert "retrieve" not in answer.casefold()
        assert any(block.get("kind") == "example" and "surface statement" in block.get("content", "") for block in response.json()["scene"]["blocks"])
    finally:
        set_tutor_provider(None)

def test_ask_another_question_recomposes_active_scene(client):
    document = _document_with_note(client)
    session = client.post(f"/documents/{document['id']}/learn-sessions", json={"goal": "understand", "familiarity": "new"}).json()
    before = session["scene"]
    response = client.post(f"/learn-sessions/{session['id']}/ask", json={"message": "Ask me another question."})
    assert response.status_code == 200
    scene = response.json()["scene"]
    assert scene["revision"] > before["revision"]
    assert scene.get("responseInteractionId") != before.get("responseInteractionId")
    assert any(block.get("kind") == "practice" for block in scene["blocks"])


def test_ask_show_visual_synthesizes_grounded_visual_from_source_component(client):
    source = client.post("/sources", json={"type": "website", "url": "https://example.com/visual"}).json()
    document = client.post("/documents", json={"source_id": source["id"], "title": "Mechanism material", "content": "A source-grounded comparison."}).json()
    note = {
        "title": "Mechanism material", "sectionNotes": [{
            "id": "s-visual", "title": "Two mechanisms", "bigIdea": "Two mechanisms produce different outcomes.",
            "sourceBlockIds": ["b-visual"], "keyTakeaways": ["The mechanisms must be distinguished."],
            "components": [{"kind": "comparison", "title": "Compare mechanisms", "dimensions": ["effect"], "items": [
                {"id": "m1", "name": "Mechanism A", "values": {"effect": "increases output"}},
                {"id": "m2", "name": "Mechanism B", "values": {"effect": "reduces output"}},
            ]}],
        }],
    }
    client.post("/notes", json={"title": "Mechanism note", "content_type": "section_note", "document_id": document["id"], "content": json.dumps(note)})
    session = client.post(f"/documents/{document['id']}/learn-sessions", json={"goal": "understand", "familiarity": "new"}).json()
    response = client.post(f"/learn-sessions/{session['id']}/ask", json={"message": "Show me visually"})
    assert response.status_code == 200
    scene = response.json()["scene"]
    visual = [block for block in scene["blocks"] if block.get("kind") in {"visual", "animation"}]
    assert visual and visual[0].get("visualSpec", {}).get("nodes")
    assert response.json()["visualAction"]["type"] == "show_visual"
    first_stage = scene.get("visualState", {}).get("stage", 0)
    second = client.post(f"/learn-sessions/{session['id']}/ask", json={"message": "Show me visually"})
    assert second.status_code == 200
    assert second.json()["scene"].get("visualState", {}).get("stage", 0) >= first_stage


def test_ask_show_visual_can_add_a_new_grounded_visual_surface(client):
    source = client.post("/sources", json={"type": "website", "url": "https://example.com/multi-visual"}).json()
    document = client.post("/documents", json={"source_id": source["id"], "title": "Paired mechanisms", "content": "Two source-grounded views explain the mechanism."}).json()
    note = {"title": "Paired mechanisms", "sectionNotes": [
        {"id": "s-one", "title": "First view", "bigIdea": "The first mechanism increases output.", "sourceBlockIds": ["b-one"], "keyTakeaways": ["First mechanism"], "components": [{"kind": "comparison", "title": "Increase pathway", "dimensions": ["effect"], "items": [{"id": "a", "name": "Input", "values": {"effect": "increases output"}}, {"id": "b", "name": "Result", "values": {"effect": "higher output"}}]}, {"kind": "flow", "title": "Limiting pathway", "stages": [{"id": "start", "label": "Input"}, {"id": "end", "label": "Limited output"}]}]},
        {"id": "s-two", "title": "Second view", "bigIdea": "The second mechanism limits output.", "sourceBlockIds": ["b-two"], "keyTakeaways": ["Second mechanism"], "components": [{"kind": "comparison", "title": "Limiting pathway", "dimensions": ["effect"], "items": [{"id": "c", "name": "Input", "values": {"effect": "limits output"}}, {"id": "d", "name": "Result", "values": {"effect": "lower output"}}]}]},
    ]}
    client.post("/notes", json={"title": "Paired note", "content_type": "section_note", "document_id": document["id"], "content": json.dumps(note)})
    session = client.post(f"/documents/{document['id']}/learn-sessions", json={"goal": "understand", "familiarity": "new"}).json()
    first = client.post(f"/learn-sessions/{session['id']}/ask", json={"message": "Show me visually"})
    assert first.status_code == 200
    before_count = sum(block.get("kind") in {"visual", "animation"} for block in first.json()["scene"]["blocks"])
    second = client.post(f"/learn-sessions/{session['id']}/ask", json={"message": "Show me visually"})
    assert second.status_code == 200
    scene = second.json()["scene"]
    after_count = sum(block.get("kind") in {"visual", "animation"} for block in scene["blocks"])
    assert after_count > before_count, {"before": first.json(), "after": second.json()}
    assert second.json()["visualAction"]["type"] == "add_visual"


def test_model_tutor_replans_to_a_bounded_grounded_candidate(client):
    document = _document_with_note(client)
    session = client.post(f"/documents/{document['id']}/learn-sessions", json={"goal": "solve", "familiarity": "new"}).json()
    client.post(f"/learn-sessions/{session['id']}/responses", json={})
    calls = []

    def fake_provider(_prompt, tool_name, _schema, **_kwargs):
        calls.append(tool_name)
        if tool_name == "learn_tutor_decision":
            concept = re.search(r"objectiveId['\"]?:\s*['\"]([^'\"]+)", _prompt).group(1)
            candidates = re.findall(r"\{'id': '([^']+)'", _prompt)
            repair = next(candidate for candidate in candidates if candidate.startswith("repair-"))
            return {"hypothesis": "The learner needs a source-specific recheck.", "diagnosis": "KNOWLEDGE_GAP", "confidence": 0.8, "pedagogicalGoal": "BUILD_INTUITION", "pedagogicalStrategy": "CONCRETE_EXAMPLE", "teachingAction": "give_example", "targetConcept": concept, "interactionType": "short_answer", "scaffoldLevel": "GUIDED", "visualAction": None, "prerequisiteBranch": None, "actions": [{"tool": "give_example", "arguments": {}}], "expectedEvidence": "The learner states the material's actual idea.", "transitionMessage": "Let’s use a concrete source example.", "nextStepId": repair, "rationale": "A bounded alternate check is the safest next intervention."}
        raise AssertionError(f"unexpected provider call: {tool_name}")

    set_tutor_provider(fake_provider)
    try:
        response = client.post(f"/learn-sessions/{session['id']}/responses", json={"response": "unrelated"})
        assert response.status_code == 200
        payload = response.json()
        assert "learn_tutor_decision" in calls
        assert payload["scene"] is not None
        assert payload["scene"]["revision"] >= 1
    finally:
        set_tutor_provider(None)


def _document_with_two_sections(client):
    source = client.post("/sources", json={"type": "website", "url": "https://example.com/two-sections"}).json()
    document = client.post("/documents", json={"source_id": source["id"], "title": "Two-section material", "content": "Grounded material."}).json()
    client.post("/notes", json={
        "title": "Two-section note", "content_type": "section_note", "document_id": document["id"],
        "content": json.dumps({"title": "Two-section material", "sectionNotes": [
            {"id": "s1", "title": "First idea", "bigIdea": "The first source-grounded idea.", "sourceBlockIds": ["b1"], "keyTakeaways": ["The first idea matters."], "components": []},
            {"id": "s2", "title": "Second idea", "bigIdea": "The second source-grounded idea.", "sourceBlockIds": ["b2"], "keyTakeaways": ["The second idea matters."], "components": []},
        ]}),
    })
    return document


def test_ask_lucent_uses_the_active_scenes_objective_not_the_stale_index(client):
    # Regression: ask_lucent() resolved its "current objective" from
    # session.objective_index, a legacy column the authoritative runtime
    # never advances. Once the learner moved on to a later objective, Ask
    # Lucent kept answering questions about the *first* objective forever.
    document = _document_with_two_sections(client)
    session = client.post(f"/documents/{document['id']}/learn-sessions", json={"goal": "understand", "familiarity": "new"}).json()
    first_objective_id = session["scene"]["objectiveId"]

    from sqlalchemy.orm import Session as SASession
    from app.database import engine
    from app.models.learn import LearnSession as LearnSessionModel

    with SASession(engine) as db:
        row = db.get(LearnSessionModel, session["id"])
        objective_ids = [o["id"] for o in row.plan["objectives"]]
        second_objective_id = next(oid for oid in objective_ids if oid != first_objective_id)
        state = dict(row.state or {})
        state["currentObjectiveId"] = second_objective_id
        current_scene = dict(state["currentScene"])
        current_scene["objectiveId"] = second_objective_id
        current_scene["objective"] = "Second idea"
        state["currentScene"] = current_scene
        row.state = state
        assert row.objective_index == 0  # the stale column is untouched, as the runtime leaves it
        db.commit()

    seen_prompts = []

    def fake_provider(prompt, tool_name, _schema, **_kwargs):
        seen_prompts.append(prompt)
        return {"answer": "Grounded answer.", "toolCalls": [], "sourceSectionIds": [], "sourceBlockIds": []}

    set_tutor_provider(fake_provider)
    try:
        response = client.post(f"/learn-sessions/{session['id']}/ask", json={"message": "Why does this matter?"})
        assert response.status_code == 200
    finally:
        set_tutor_provider(None)
    assert seen_prompts, "the ask model should have been called"
    combined = " ".join(seen_prompts)
    assert "Second idea" in combined
    assert "First idea" not in combined


def test_objective_progress_reflects_the_active_scene_not_the_stale_index(client):
    # Regression: `objectiveIndex` in the session payload was read straight
    # from the DB column, which the runtime never advances. The "Objective X
    # of Y" progress shown in the UI stayed frozen at 1 even after the
    # learner had genuinely moved on to a later objective.
    document = _document_with_two_sections(client)
    session = client.post(f"/documents/{document['id']}/learn-sessions", json={"goal": "understand", "familiarity": "new"}).json()
    assert session["objectiveIndex"] == 0
    first_objective_id = session["scene"]["objectiveId"]

    from sqlalchemy.orm import Session as SASession
    from app.database import engine
    from app.models.learn import LearnSession as LearnSessionModel

    with SASession(engine) as db:
        row = db.get(LearnSessionModel, session["id"])
        objective_ids = [o["id"] for o in row.plan["objectives"]]
        second_objective_id = next(oid for oid in objective_ids if oid != first_objective_id)
        state = dict(row.state or {})
        state["currentObjectiveId"] = second_objective_id
        current_scene = dict(state["currentScene"])
        current_scene["objectiveId"] = second_objective_id
        state["currentScene"] = current_scene
        row.state = state
        db.commit()

    refreshed = client.get(f"/learn-sessions/{session['id']}").json()
    assert refreshed["objectiveIndex"] == 1
