from __future__ import annotations

import json
import re
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, get_args
from uuid import UUID, uuid4

from conftest import TestSessionLocal as SessionLocal
from app.models.learn import LearnSession
from app.models.learning_block import DocumentSourceIndex, PersistedLearningBlock
from app.routers.learn import _concept_for, _parse_step, _tutor_observation
from app.schemas.learn import TutorToolName
from app.services.embeddings import DeterministicEmbeddingProvider, set_embedding_provider
from app.services.learn_engine import student_facing_quality_issues
from app.services.learn_tutor import set_tutor_provider


@dataclass
class TutorTraceTurn:
    observation: dict[str, Any]
    decision: dict[str, Any]
    tool_calls: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    selected_step: dict[str, Any] | None
    selected_action: dict[str, Any] | None
    learner_response: dict[str, Any]
    evidence_update: list[dict[str, Any]]
    session_state: dict[str, Any]
    status_code: int
    feedback: str | None = None


@dataclass
class TutorScenarioTrace:
    name: str
    turns: list[TutorTraceTurn] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "turns": [turn.__dict__ for turn in self.turns]}


class FakeTutorProvider:
    """Structured fake exercising the same provider boundary as production."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, prompt: str, tool_name: str, _schema: dict, **_kwargs):
        self.calls.append(tool_name)
        if tool_name == "learn_response_evaluation":
            response = prompt.rsplit("Learner response:", 1)[-1].strip().casefold()
            if "independent correct" in response or "transfer success" in response:
                return {"result": "correct", "confidence": 0.94, "misconception": None, "evidence": "The response independently explains the source-supported relationship.", "studentMessage": "Nice work -- that's exactly the relationship.", "remediationCategory": "none"}
            if "partially" in response or "not sure" in response:
                return {"result": "partially_correct", "confidence": 0.72, "misconception": None, "evidence": "The response contains one source-supported element but omits the consequence.", "studentMessage": "You're partway there -- now connect that to what it causes.", "remediationCategory": "simplify"}
            if "i don't know" in response or "i do not know" in response:
                return {"result": "insufficient_evidence", "confidence": 0.92, "misconception": None, "evidence": "The learner explicitly reported uncertainty.", "studentMessage": "No problem -- let's build the idea together first.", "remediationCategory": "example"}
            return {"result": "incorrect", "confidence": 0.91, "misconception": "Reverses the source-supported cause and effect", "evidence": "The response states the opposite direction from the source evidence.", "studentMessage": "Not quite -- the direction is reversed from what the material describes.", "remediationCategory": "change_modality"}
        if tool_name == "learn_tutor_decision":
            concept_match = re.search(r"objectiveId['\"]?:\s*['\"]([^'\"]+)", prompt)
            concept_id = concept_match.group(1) if concept_match else "concept"
            return {
                "hypothesis": "The learner needs a different grounded representation before another check.",
                "diagnosis": "MISCONCEPTION",
                "confidence": 0.86,
                "pedagogicalGoal": "CORRECT_MISCONCEPTION",
                "pedagogicalStrategy": "CONTRAST_CASE",
                "teachingAction": "give_example",
                "targetConcept": concept_id,
                "interactionType": None,
                "scaffoldLevel": "GUIDED",
                "visualAction": None,
                "prerequisiteBranch": None,
                "actions": [{"tool": "inspect_learner_memory", "arguments": {"conceptId": concept_id}}],
                "expectedEvidence": "A source-grounded explanation without assistance.",
                "transitionMessage": "I’m changing the representation before checking this again.",
                "nextStepId": None,
                "rationale": "The previous representation did not resolve the learner's misconception.",
            }
        if tool_name == "ask_lucent":
            return {
                "answer": "The source explains that the change causes the stated outcome; focus on that direction of cause and effect.",
                "toolCalls": [{"tool": "request_example", "arguments": {}}],
                "sourceSectionIds": ["s1"],
                "sourceBlockIds": ["b1"],
            }
        raise AssertionError(f"Unexpected provider tool: {tool_name}")


def create_source_material(client, *, title: str = "Pendulum energy", goal: str = "solve") -> tuple[dict, dict]:
    source = client.post("/sources", json={"type": "website", "url": "https://example.com/agent-scenario"}).json()
    document = client.post("/documents", json={"source_id": source["id"], "title": title, "content": "Energy changes form while total mechanical energy is conserved."}).json()
    note = {
        "title": title,
        "sectionNotes": [{
            "id": "s1",
            "title": title,
            "bigIdea": "As a pendulum falls, gravitational potential energy becomes kinetic energy while total mechanical energy remains conserved.",
            "sourceBlockIds": ["b1"],
            "keyTakeaways": ["Speed and kinetic energy are greatest at the bottom of the swing."],
            "components": [{
                "kind": "worked_example",
                "title": "Energy conversion",
                "problem": "A pendulum falls from a turning point toward the bottom.",
                "result": "kinetic energy increases as potential energy decreases",
                "steps": [{"order": 1, "description": "Identify the loss in height."}, {"order": 2, "description": "Relate that loss to increased speed."}],
            }],
        }],
    }
    generation = uuid4()
    note["sourceGeneration"] = str(generation)
    source_text = "As a pendulum falls, gravitational potential energy becomes kinetic energy while total mechanical energy remains conserved. Speed and kinetic energy are greatest at the bottom of the swing."
    digest = hashlib.sha256(source_text.encode()).hexdigest()
    provider = DeterministicEmbeddingProvider()
    with SessionLocal() as db:
        db.add(DocumentSourceIndex(
            document_id=document["id"], generation_id=generation, corpus_hash=digest,
            normalization_version="scenario-v1", segmentation_version="scenario-v1",
            status="READY", provider=provider.metadata.provider, model=provider.metadata.model,
            dimensions=provider.metadata.dimensions, block_count=1, embedded_count=1,
            indexed_at=datetime.now(timezone.utc),
        ))
        db.add(PersistedLearningBlock(
            document_id=document["id"], block_id="b1", generation_id=generation,
            ordinal=0, block_type="text", title=title, text=source_text,
            character_count=len(source_text), heading_ancestry=[], normalized_block_ids=["b1"],
            section_ids=["s1"], source={"page_start": 1, "page_end": 1},
            segmentation={"method": "scenario", "version": "scenario-v1"}, attachments=[],
            content_hash=digest, embedding_input_hash=digest,
            embedding=provider.embed_documents([source_text])[0], embedded_at=datetime.now(timezone.utc),
        ))
        db.commit()
    client.post("/notes", json={"title": title, "content_type": "section_note", "document_id": document["id"], "content": json.dumps(note)})
    session = client.post(f"/documents/{document['id']}/learn-sessions", json={"goal": goal, "familiarity": "new", "restart": True}).json()
    return document, session


def response_for(step: dict[str, Any] | None, *, text: str = "I don't know") -> dict[str, Any]:
    # Scene-only API responses no longer expose the legacy `step` field. Keep
    # scenario scripts readable by accepting a scene payload when supplied.
    if step and "blocks" in step:
        active_id = step.get("responseInteractionId")
        step = next((block.get("step") for block in step.get("blocks", []) if block.get("kind") == "practice" and block.get("step") and active_id and block["step"].get("id") == active_id), None)
        # Public LearnStepView may omit the private grading shape.  The
        # runtime still exposes the authoritative interaction identity, so a
        # free-form response is the safe scripted input for that target.
        if step is None and active_id:
            return {"response": text}
    if not step or step.get("type") in {"teach", "walkthrough"}:
        return {}
    if step.get("type") in {"multiple_choice", "prediction"}:
        return {"optionId": "not-a-valid-answer"}
    if step.get("type") == "ordering":
        return {"orderedIds": list(reversed([item["id"] for item in step.get("items", [])]))}
    if step.get("type") in {"matching", "labeling"}:
        return {"response": json.dumps({item["id"]: "not-a-valid-answer" for item in step.get("items", [])})}
    return {"response": text}


def _session_snapshot(session_id: str) -> tuple[LearnSession, dict[str, Any]]:
    with SessionLocal() as db:
        session = db.get(LearnSession, UUID(session_id))
        assert session is not None
        state = dict(session.state or {})
        # Detach the values used by assertions before the session closes.
        session.plan = json.loads(json.dumps(session.plan))
        return session, json.loads(json.dumps(state))


def run_turn(client, trace: TutorScenarioTrace, session_payload: dict[str, Any], learner_payload: dict[str, Any]) -> dict[str, Any]:
    before, state_before = _session_snapshot(session_payload["id"])
    def active_payload(state: dict[str, Any]):
        return (state.get("currentScenePrivate") or {}).get("interaction")
    # A teaching-only scene must be advanced before a scripted learner can
    # answer. This mirrors the real frontend's Continue event.
    if learner_payload and not active_payload(state_before):
        client.post(f"/learn-sessions/{session_payload['id']}/responses", json={"eventType": "CONTINUE"})
        before, state_before = _session_snapshot(session_payload["id"])
    objective_id = state_before.get("currentObjectiveId")
    objective = next((item for item in before.plan["objectives"] if str(item.get("id")) == str(objective_id)), before.plan["objectives"][before.objective_index])
    raw_step = active_payload(state_before)
    step = _parse_step(raw_step) if raw_step else None
    concept = next((item for item in state_before.get("concepts", []) if item.get("conceptId") == objective["id"]), _concept_for(before, objective))
    observation = _tutor_observation(before, objective, concept, step, state_before).model_dump(by_alias=True)
    scene = state_before.get("currentScene") or {}
    request_payload = dict(learner_payload)
    request_payload.setdefault("sceneId", scene.get("id"))
    request_payload.setdefault("sceneRevision", scene.get("revision"))
    request_payload.setdefault("interactionId", raw_step.get("id") if raw_step else None)
    request_payload.setdefault("eventType", "RESPONSE" if raw_step and learner_payload else "CONTINUE")
    response = client.post(f"/learn-sessions/{session_payload['id']}/responses", json=request_payload)
    payload = response.json()
    _, state_after = _session_snapshot(session_payload["id"])
    decision = dict(state_after.get("lastTutorDecision") or {})
    selected_step = ((state_after.get("currentScenePrivate") or {}).get("interaction")) or payload.get("step")
    if selected_step is None:
        scene_payload = payload.get("scene") or {}
        active_id = scene_payload.get("responseInteractionId")
        selected_step = next((block.get("step") for block in scene_payload.get("blocks", []) if block.get("kind") == "practice" and block.get("step") and active_id and block["step"].get("id") == active_id), None)
    trace.turns.append(TutorTraceTurn(
        observation=observation,
        decision=decision,
        tool_calls=list(decision.get("actions") or []),
        tool_results=list(state_after.get("lastTutorToolResults") or []),
        selected_step=selected_step,
        selected_action=payload.get("action"),
        learner_response=learner_payload,
        evidence_update=list(payload.get("conceptStates") or []),
        session_state=state_after,
        status_code=response.status_code,
        feedback=payload.get("feedback"),
    ))
    return payload


def assert_trace_invariants(trace: TutorScenarioTrace) -> None:
    assert trace.turns, trace.name
    seen_step_ids: set[str] = set()
    previous_response_step: str | None = None
    allowed_tools = set(get_args(TutorToolName))
    allowed_arguments = {"stepId", "conceptId", "stage", "nodeId", "reason"}
    for turn in trace.turns:
        assert turn.status_code < 500
        if turn.selected_step:
            step_id = str(turn.selected_step["id"])
            assert len(step_id) <= 60
            assert not re.search(r"repair-.+repair-|prerequisite-.+prerequisite-", step_id)
            assert turn.selected_step.get("sourceSectionIds") or turn.selected_step.get("sourceBlockIds")
            seen_step_ids.add(step_id)
            if turn.learner_response and previous_response_step:
                    assert step_id != previous_response_step, f"failed interaction repeated without an intervening teaching change: {step_id} previous={previous_response_step}"
            previous_response_step = step_id if turn.learner_response else None
        if turn.selected_action:
            assert len(str(turn.selected_action["id"])) <= 60
            assert turn.selected_action.get("stepId") == (turn.selected_step or {}).get("id")
        assert len(turn.tool_calls) <= 4
        assert all(call.get("tool") in allowed_tools for call in turn.tool_calls)
        assert all(set((call.get("arguments") or {})) <= allowed_arguments for call in turn.tool_calls)
        assert all(result.get("status") in {"accepted", "applied", "rejected"} for result in turn.tool_results)
        assert len(turn.session_state.get("branchStack", [])) <= 4
        assert len(turn.session_state.get("recentAttempts", [])) <= 8
        assert len(turn.session_state.get("previousTutorActions", [])) <= 8
        if turn.feedback:
            # Internal grading rationale (analytical, third-person) must never
            # reach the public feedback text -- only a natural, second-person
            # student_message (or the deterministic evaluator's own
            # learner-appropriate evidence text) may.
            lowered = turn.feedback.casefold()
            assert "the learner" not in lowered, f"internal grading language leaked into public feedback: {turn.feedback!r}"
            assert "non-response" not in lowered, f"internal grading language leaked into public feedback: {turn.feedback!r}"
    # A stress run may legitimately compose fresh bounded retries; persisted
    # history is capped separately while IDs remain bounded and non-recursive.
    assert len(seen_step_ids) <= 64


def provider_context(provider: FakeTutorProvider):
    class _ProviderContext:
        def __enter__(self):
            set_tutor_provider(provider)
            set_embedding_provider(DeterministicEmbeddingProvider())
            return provider

        def __exit__(self, *_args):
            set_tutor_provider(None)
            set_embedding_provider(None)
    return _ProviderContext()
