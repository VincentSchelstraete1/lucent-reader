from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, get_args
from uuid import UUID

from app.database import SessionLocal
from app.models.learn import LearnSession
from app.routers.learn import _concept_for, _parse_step, _tutor_observation
from app.schemas.learn import TutorToolName
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
                return {"result": "correct", "confidence": 0.94, "misconception": None, "evidence": "The response independently explains the source-supported relationship.", "remediationCategory": "none"}
            if "partially" in response or "not sure" in response:
                return {"result": "partially_correct", "confidence": 0.72, "misconception": None, "evidence": "The response contains one source-supported element but omits the consequence.", "remediationCategory": "simplify"}
            if "i don't know" in response or "i do not know" in response:
                return {"result": "insufficient_evidence", "confidence": 0.92, "misconception": None, "evidence": "The learner explicitly reported uncertainty.", "remediationCategory": "example"}
            return {"result": "incorrect", "confidence": 0.91, "misconception": "The learner reverses the source-supported cause and effect.", "evidence": "The response states the opposite direction from the source evidence.", "remediationCategory": "change_modality"}
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
    client.post("/notes", json={"title": title, "content_type": "section_note", "document_id": document["id"], "content": json.dumps(note)})
    session = client.post(f"/documents/{document['id']}/learn-sessions", json={"goal": goal, "familiarity": "new", "restart": True}).json()
    return document, session


def response_for(step: dict[str, Any] | None, *, text: str = "I don't know") -> dict[str, Any]:
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
    objective = before.plan["objectives"][before.objective_index]
    step = _parse_step(objective["steps"][before.step_index])
    concept = next((item for item in state_before.get("concepts", []) if item.get("conceptId") == objective["id"]), _concept_for(before, objective))
    observation = _tutor_observation(before, objective, concept, step, state_before).model_dump(by_alias=True)
    response = client.post(f"/learn-sessions/{session_payload['id']}/responses", json=learner_payload)
    payload = response.json()
    _, state_after = _session_snapshot(session_payload["id"])
    decision = dict(state_after.get("lastTutorDecision") or {})
    trace.turns.append(TutorTraceTurn(
        observation=observation,
        decision=decision,
        tool_calls=list(decision.get("actions") or []),
        tool_results=list(state_after.get("lastTutorToolResults") or []),
        selected_step=payload.get("step"),
        selected_action=payload.get("action"),
        learner_response=learner_payload,
        evidence_update=list(payload.get("conceptStates") or []),
        session_state=state_after,
        status_code=response.status_code,
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
                assert step_id != previous_response_step, "failed interaction repeated without an intervening teaching change"
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
    assert len(seen_step_ids) <= 12


def provider_context(provider: FakeTutorProvider):
    class _ProviderContext:
        def __enter__(self):
            set_tutor_provider(provider)
            return provider

        def __exit__(self, *_args):
            set_tutor_provider(None)
    return _ProviderContext()
