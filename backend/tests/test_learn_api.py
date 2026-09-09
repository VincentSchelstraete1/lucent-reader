import json
import re
import hashlib
import uuid
import threading
import time
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.learning_block import DocumentSourceIndex, PersistedLearningBlock
from app.models.auth import User
from app.models.learn import LearnSession
from app.routers.learn import _get_owned_session_for_mutation
from app.services.embeddings import DeterministicEmbeddingProvider, set_embedding_provider
from app.services.learn_tutor import set_tutor_provider
from app.services.learn_engine import build_remediation_step
from app.schemas.learn import MultipleChoiceStep
from tests.conftest import TestSessionLocal


@pytest.fixture(autouse=True)
def _offline_source_embeddings():
    provider = DeterministicEmbeddingProvider()
    set_embedding_provider(provider)
    try:
        yield
    finally:
        set_embedding_provider(None)


def _save_indexed_note(client, document: dict, *, title: str, note: dict):
    generation = uuid.uuid4()
    note = dict(note)
    note["sourceGeneration"] = str(generation)
    provider = DeterministicEmbeddingProvider()
    records = []
    for ordinal, section in enumerate(note.get("sectionNotes", [])):
        block_id = str((section.get("sourceBlockIds") or [f"block-{ordinal}"])[0])
        text = " ".join(filter(None, [str(section.get("title") or ""), str(section.get("bigIdea") or ""), *map(str, section.get("keyTakeaways") or [])])).strip()
        records.append((ordinal, block_id, str(section.get("id") or f"section-{ordinal}"), text))
    vectors = provider.embed_documents([record[3] for record in records])
    with TestSessionLocal() as db:
        db.add(DocumentSourceIndex(
            document_id=document["id"], generation_id=generation,
            corpus_hash=hashlib.sha256("|".join(record[3] for record in records).encode()).hexdigest(),
            normalization_version="test-v1", segmentation_version="test-v1",
            status="READY", provider=provider.metadata.provider, model=provider.metadata.model,
            dimensions=provider.metadata.dimensions, block_count=len(records), embedded_count=len(records),
            indexed_at=datetime.now(timezone.utc),
        ))
        for (ordinal, block_id, section_id, text), vector in zip(records, vectors):
            digest = hashlib.sha256(text.encode()).hexdigest()
            db.add(PersistedLearningBlock(
                document_id=document["id"], block_id=block_id, generation_id=generation,
                ordinal=ordinal, block_type="text", title=title, text=text,
                character_count=len(text), heading_ancestry=[], normalized_block_ids=[block_id],
                section_ids=[section_id], source={"page_start": ordinal + 1, "page_end": ordinal + 1},
                segmentation={"method": "test", "version": "test-v1"}, attachments=[],
                content_hash=digest, embedding_input_hash=digest, embedding=vector,
                embedded_at=datetime.now(timezone.utc),
            ))
        db.commit()
    return client.post("/notes", json={
        "title": title, "content_type": "section_note", "document_id": document["id"],
        "content": json.dumps(note),
    })


def _document_with_note(client):
    source = client.post("/sources", json={"type": "website", "url": "https://example.com/learn"}).json()
    document = client.post("/documents", json={"source_id": source["id"], "title": "Learn material", "content": "Grounded material."}).json()
    _save_indexed_note(client, document, title="Learn note", note={"title": "Learn material", "sectionNotes": [{
            "id": "s1", "title": "Core idea", "bigIdea": "A source-grounded idea.", "sourceBlockIds": ["b1"],
            "keyTakeaways": ["The idea matters."], "components": [],
        }]})
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

    # The initial authoritative scene already owns the active response.  The
    # real frontend never submits an empty RESPONSE to advance past it.
    next_step = session
    active_id = next_step["scene"].get("responseInteractionId")
    if active_id:
        active_block = next(block for block in next_step["scene"]["blocks"] if (block.get("step") or {}).get("id") == active_id)
        assert active_block["step"]["hintsAvailable"] > 0, active_block
        hint = client.post(f"/learn-sessions/{session['id']}/hints", json={"interactionId": active_id}).json()
        assert "detail" not in hint, hint
        assert hint["hintsUsed"] == 1

    wrong = client.post(f"/learn-sessions/{session['id']}/responses", json={"interactionId": active_id, "eventType": "RESPONSE", "response": "unrelated"}).json()
    if active_id:
        # Remediation is an instructional scene, so its top-level tone is
        # informational even though the attempt itself was incorrect.
        assert wrong["feedbackKind"] == "info", wrong
        assert wrong["scene"] is not None
        assert wrong["scene"]["revision"] > next_step["scene"]["revision"]
        assert any(block["kind"] == "explanation" for block in wrong["scene"]["blocks"])
    # The authoritative scene carries the pedagogical change; the legacy
    # action envelope is intentionally empty during scene-only runtime.
    assert wrong["scene"] is not None

    remediation_id = wrong["scene"].get("responseInteractionId")
    remediation = client.post(
        f"/learn-sessions/{session['id']}/responses",
        json={
            "sceneId": wrong["scene"]["id"],
            "sceneRevision": wrong["scene"]["revision"],
            "interactionId": remediation_id,
            "eventType": "RESPONSE",
            "response": "the source-grounded relationship",
        },
    ).json()
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


def test_stale_scene_mutations_are_rejected_without_changing_authoritative_state(client):
    document = _document_with_note(client)
    session = client.post(
        f"/documents/{document['id']}/learn-sessions",
        json={"goal": "understand", "familiarity": "new"},
    ).json()
    stale = {"sceneId": session["scene"]["id"], "sceneRevision": session["scene"]["revision"]}
    advanced = client.post(
        f"/learn-sessions/{session['id']}/responses",
        json={
            **stale,
            "interactionId": session["scene"].get("responseInteractionId"),
            "eventType": "RESPONSE",
            "response": "an intentionally incomplete answer",
        },
    )
    assert advanced.status_code == 200
    authoritative = advanced.json()["scene"]
    assert authoritative["revision"] > stale["sceneRevision"]

    stale_requests = (
        (f"/learn-sessions/{session['id']}/responses", {**stale, "eventType": "CONTINUE"}),
        (f"/learn-sessions/{session['id']}/ask", {**stale, "message": "Explain this differently"}),
        (f"/learn-sessions/{session['id']}/hints", stale),
        (f"/learn-sessions/{session['id']}/stop", stale),
    )
    for path, payload in stale_requests:
        response = client.post(path, json=payload)
        assert response.status_code == 409, (path, response.text)

    persisted = client.get(f"/learn-sessions/{session['id']}").json()
    assert persisted["status"] == "active"
    assert persisted["scene"] == authoritative


def test_concurrent_session_mutations_serialize_from_latest_state(client):
    document = _document_with_note(client)
    created = client.post(
        f"/documents/{document['id']}/learn-sessions",
        json={"goal": "understand", "familiarity": "new"},
    ).json()
    session_id = uuid.UUID(created["id"])
    first_locked = threading.Event()
    second_attempting = threading.Event()
    errors: list[BaseException] = []

    def mutate(marker: str, wait_for_first: bool = False):
        try:
            if wait_for_first:
                assert first_locked.wait(timeout=5)
                second_attempting.set()
            with TestSessionLocal() as db:
                user = db.execute(select(User).where(User.email == "test@lucent.local")).scalar_one()
                row = _get_owned_session_for_mutation(db, session_id, user)
                state = dict(row.state or {})
                state["concurrencyMarkers"] = [*(state.get("concurrencyMarkers") or []), marker]
                row.state = state
                if not wait_for_first:
                    first_locked.set()
                    assert second_attempting.wait(timeout=5)
                    time.sleep(0.1)
                db.commit()
        except BaseException as exc:  # surface thread failures in the test
            errors.append(exc)

    first = threading.Thread(target=mutate, args=("first",))
    second = threading.Thread(target=mutate, args=("second", True))
    first.start(); second.start()
    first.join(timeout=10); second.join(timeout=10)
    assert not first.is_alive() and not second.is_alive()
    assert errors == []
    with TestSessionLocal() as db:
        row = db.get(LearnSession, session_id)
        assert row.state["concurrencyMarkers"] == ["first", "second"]


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


def test_legacy_unindexed_session_cannot_use_generated_notes_as_ask_evidence(client):
    source = client.post("/sources", json={"type": "website", "url": "https://example.com/legacy"}).json()
    document = client.post("/documents", json={"source_id": source["id"], "title": "Legacy material", "content": "Original source was not indexed."}).json()
    client.post("/notes", json={
        "title": "Legacy generated note", "content_type": "section_note", "document_id": document["id"],
        "content": json.dumps({"title": "Legacy", "sectionNotes": [{
            "id": "s1", "title": "Generated summary", "bigIdea": "This model prose must not become evidence.",
            "sourceBlockIds": ["missing-block"], "keyTakeaways": ["Generated only"], "components": [],
        }]}),
    })
    session = client.post(f"/documents/{document['id']}/learn-sessions", json={"goal": "understand", "familiarity": "new"}).json()
    response = client.post(f"/learn-sessions/{session['id']}/ask", json={"message": "Explain this"})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "source_not_indexed"

def test_ask_example_replaces_provider_retrieval_narration_with_grounded_content(client):
    source = client.post("/sources", json={"type": "website", "url": "https://example.com/satire"}).json()
    document = client.post("/documents", json={"source_id": source["id"], "title": "Satire material", "content": "A source-grounded comparison."}).json()
    note = {"title": "Satire", "sectionNotes": [{"id": "satire", "title": "Satire as critique", "bigIdea": "Satire exposes hypocrisy through exaggerated sincere claims.", "sourceBlockIds": ["b1"], "components": [{"kind": "comparison", "items": [{"id": "surface", "name": "surface statement", "values": {"role": "sounds sincere"}}, {"id": "critique", "name": "underlying critique", "values": {"role": "exposes hypocrisy"}}]}]}]}
    _save_indexed_note(client, document, title="Satire", note=note)
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

def test_ask_another_question_adds_inline_interaction_without_replacing_primary(client):
    document = _document_with_note(client)
    session = client.post(f"/documents/{document['id']}/learn-sessions", json={"goal": "understand", "familiarity": "new"}).json()
    before = session["scene"]
    response = client.post(f"/learn-sessions/{session['id']}/ask", json={"message": "Ask me another question."})
    assert response.status_code == 200
    scene = response.json()["scene"]
    assert scene["revision"] > before["revision"]
    assert scene.get("responseInteractionId") == before.get("responseInteractionId")
    assert scene.get("inlineInteraction")
    assert scene["inlineInteraction"]["id"] != before.get("responseInteractionId")
    assert any(block.get("kind") == "practice" and block.get("step", {}).get("id") == before.get("responseInteractionId") for block in scene["blocks"])


def test_ask_question_difficulty_intents_shape_grounded_followups(client):
    document = _document_with_note(client)
    session = client.post(f"/documents/{document['id']}/learn-sessions", json={"goal": "understand", "familiarity": "new"}).json()
    simpler = client.post(f"/learn-sessions/{session['id']}/ask", json={"message": "Ask me a simpler question"}).json()
    simple = next(block["step"] for block in simpler["scene"]["blocks"] if block["kind"] == "practice")
    assert simple["type"] == "multiple_choice"
    assert len(simple["options"]) == 3
    assert not simple["options"][0]["label"].casefold().startswith(("explain ", "apply ", "recall "))
    assert simple["options"][0]["label"] == "A source-grounded idea."
    harder = client.post(f"/learn-sessions/{session['id']}/ask", json={"message": "Ask me a harder question"}).json()
    hard = harder["scene"]["inlineInteraction"]
    assert hard["type"] == "short_answer"
    assert "new situation" in hard["prompt"]
    assert harder["scene"]["responseInteractionId"] == simpler["scene"]["responseInteractionId"]


def test_ask_inline_interaction_can_be_checked_without_advancing_primary(client):
    document = _document_with_note(client)
    session = client.post(f"/documents/{document['id']}/learn-sessions", json={"goal": "understand", "familiarity": "new"}).json()
    before_id = session["scene"]["responseInteractionId"]
    asked = client.post(f"/learn-sessions/{session['id']}/ask", json={"message": "Ask me another question"}).json()
    inline = asked["scene"]["inlineInteraction"]
    checked = client.post(f"/learn-sessions/{session['id']}/ask-interactions/{inline['id']}/responses", json={"response": "Core idea"})
    assert checked.status_code == 200
    result = checked.json()
    assert result["scene"]["responseInteractionId"] == before_id
    assert result["scene"].get("inlineInteraction") is None
    assert any(block["kind"] == "feedback" for block in result["scene"]["blocks"])


def test_ask_walkthrough_adds_guided_steps_tied_to_active_task(client):
    document = _document_with_note(client)
    session = client.post(f"/documents/{document['id']}/learn-sessions", json={"goal": "understand", "familiarity": "new"}).json()
    response = client.post(f"/learn-sessions/{session['id']}/ask", json={"message": "Walk me through it"})
    assert response.status_code == 200
    scene = response.json()["scene"]
    guided = next(block for block in scene["blocks"] if block["kind"] == "worked_example")
    assert "one step at a time" in guided["content"]
    assert scene["responseInteractionId"] == session["scene"]["responseInteractionId"]


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
    _save_indexed_note(client, document, title="Mechanism note", note=note)
    session = client.post(f"/documents/{document['id']}/learn-sessions", json={"goal": "understand", "familiarity": "new"}).json()
    response = client.post(f"/learn-sessions/{session['id']}/ask", json={"message": "Show me visually"})
    assert response.status_code == 200
    scene = response.json()["scene"]
    visual = [block for block in scene["blocks"] if block.get("kind") in {"visual", "animation"}]
    assert visual and visual[0].get("visualSpec", {}).get("nodes")
    assert response.json()["visualAction"]["type"] in {"show_visual", "add_visual"}
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
    _save_indexed_note(client, document, title="Paired note", note=note)
    session = client.post(f"/documents/{document['id']}/learn-sessions", json={"goal": "understand", "familiarity": "new"}).json()
    first = client.post(f"/learn-sessions/{session['id']}/ask", json={"message": "Show me visually"})
    assert first.status_code == 200
    before_count = sum(block.get("kind") in {"visual", "animation"} for block in first.json()["scene"]["blocks"])
    second = client.post(f"/learn-sessions/{session['id']}/ask", json={"message": "Show me visually"})
    assert second.status_code == 200
    scene = second.json()["scene"]
    after_count = sum(block.get("kind") in {"visual", "animation"} for block in scene["blocks"])
    assert after_count == before_count == 1, {"before": first.json(), "after": second.json()}
    assert second.json()["visualAction"]["type"] == "add_visual"
    active_objective = next(item for item in session["conceptStates"] if item["conceptId"] == scene["objectiveId"])
    visual_block = next(block for block in scene["blocks"] if block.get("kind") in {"visual", "animation"})
    assert set(visual_block["sourceSectionIds"]) <= set(active_objective["sourceSectionIds"])


def test_grounded_scene_visual_request_survives_weak_semantic_query_without_weakening_other_refusals(client, monkeypatch):
    source = client.post("/sources", json={"type": "website", "url": "https://example.com/visual-intent"}).json()
    document = client.post("/documents", json={"source_id": source["id"], "title": "Visual mechanism", "content": "A grounded process."}).json()
    note = {"title": "Visual mechanism", "sectionNotes": [{
        "id": "s-visual", "title": "Energy pathway", "bigIdea": "Potential energy changes into kinetic energy.",
        "sourceBlockIds": ["b-visual"], "keyTakeaways": ["Energy changes form."],
        "components": [{"kind": "flow", "title": "Energy flow", "nodes": [
            {"id": "potential", "label": "Potential energy"}, {"id": "kinetic", "label": "Kinetic energy"},
        ], "edges": [{"source": "potential", "target": "kinetic", "label": "converts to"}]}],
    }]}
    _save_indexed_note(client, document, title="Visual mechanism", note=note)
    session = client.post(f"/documents/{document['id']}/learn-sessions", json={"goal": "understand", "familiarity": "new"}).json()

    from app.routers import learn as learn_router
    real_retrieve = learn_router.retrieve_source

    def weak_retrieve(*args, **kwargs):
        return replace(real_retrieve(*args, **kwargs), status=learn_router.RetrievalStatus.WEAK)

    def unsupported_provider(_prompt, tool_name, _schema, **_kwargs):
        if tool_name == "ask_lucent":
            return {"answer": "I cannot establish an answer.", "toolCalls": [], "sourceSectionIds": [], "sourceBlockIds": [], "supported": False}
        return None

    monkeypatch.setattr(learn_router, "retrieve_source", weak_retrieve)
    set_tutor_provider(unsupported_provider)
    try:
        visual = client.post(f"/learn-sessions/{session['id']}/ask", json={"message": "Show me visually"})
        assert visual.status_code == 200
        assert visual.json()["scope"] != "OUT_OF_SCOPE"
        assert visual.json()["scene"]["revision"] > session["scene"]["revision"]
        assert visual.json()["scene"]["responseInteractionId"] == session["scene"]["responseInteractionId"]
        assert visual.json()["visualAction"]["type"] in {"show_visual", "add_visual"}
        visual_scene = visual.json()["scene"]
        visual_title = next(block["visualSpec"]["title"] for block in visual_scene["blocks"] if block.get("kind") == "visual")
        practice = next(block["step"] for block in visual_scene["blocks"] if block.get("kind") == "practice")
        response = client.post(f"/learn-sessions/{session['id']}/responses", json={
            "sceneId": visual_scene["id"], "sceneRevision": visual_scene["revision"],
            "interactionId": practice["id"], "eventType": "RESPONSE",
            "orderedIds": list(reversed([item["id"] for item in practice["items"]])),
        })
        assert response.status_code == 200
        response_visual_title = next(block["visualSpec"]["title"] for block in response.json()["scene"]["blocks"] if block.get("kind") == "visual")
        assert response_visual_title == visual_title

        unsupported = client.post(f"/learn-sessions/{session['id']}/ask", json={"message": "Was the author born in Dublin?"})
        assert unsupported.status_code == 200
        assert unsupported.json()["scope"] == "OUT_OF_SCOPE"
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
    _save_indexed_note(client, document, title="Two-section note", note={"title": "Two-section material", "sectionNotes": [
            {"id": "s1", "title": "First idea", "bigIdea": "The first source-grounded idea.", "sourceBlockIds": ["b1"], "keyTakeaways": ["The first idea matters."], "components": []},
            {"id": "s2", "title": "Second idea", "bigIdea": "The second source-grounded idea.", "sourceBlockIds": ["b2"], "keyTakeaways": ["The second idea matters."], "components": []},
        ]})
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
    # Retrieval may include a semantically related neighboring source block,
    # but the authoritative observation/decision target must be the scene's
    # second objective rather than the stale objective_index column.
    assert second_objective_id in combined


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
