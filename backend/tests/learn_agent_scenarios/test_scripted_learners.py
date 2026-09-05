from __future__ import annotations

import json
import re
from copy import deepcopy
from uuid import UUID

import pytest

from app.database import SessionLocal
from app.models.learn import LearnSession
from app.routers.learn import _action_for, _append_remediation, _parse_step
from app.schemas.learn import ShortAnswerStep
from app.services.adaptive_policy import next_scaffold
from app.services.learn_engine import build_learn_plan, student_facing_quality_issues

from .harness import (
    FakeTutorProvider,
    TutorScenarioTrace,
    assert_trace_invariants,
    create_source_material,
    provider_context,
    response_for,
    run_turn,
)


@pytest.mark.parametrize("name,response", [
    ("i_dont_know", "I don't know"),
    ("uncertainty", "I'm not sure; partially"),
    ("confident_misconception", "Kinetic energy is highest at the turning point."),
    ("prerequisite_gap", "I do not know how height relates to potential energy."),
    ("math_procedural_error", "I used the right formula but substituted the height for velocity."),
])
def test_scripted_learner_replans_with_a_complete_trace(client, name, response):
    provider = FakeTutorProvider()
    with provider_context(provider):
        _, session = create_source_material(client)
        trace = TutorScenarioTrace(name)
        session = run_turn(client, trace, session, {})
        session = run_turn(client, trace, session, response_for(session.get("step"), text=response))
    assert_trace_invariants(trace)
    assert "learn_tutor_decision" in provider.calls
    assert trace.turns[-1].decision.get("pedagogicalStrategy") == "CONTRAST_CASE"
    assert trace.turns[-1].observation["sourceBlockIds"] == ["b1"]


def test_repeated_incorrect_answers_do_not_repeat_or_grow_repairs(client):
    provider = FakeTutorProvider()
    with provider_context(provider):
        _, session = create_source_material(client)
        trace = TutorScenarioTrace("repeated_incorrect")
        for _ in range(12):
            session = run_turn(client, trace, session, response_for(session.get("step"), text="confidently wrong"))
    assert_trace_invariants(trace)
    with SessionLocal() as db:
        stored = db.get(LearnSession, session["id"])
        step_ids = [raw["id"] for raw in stored.plan["objectives"][0]["steps"]]
        assert sum(step_id.startswith("repair-") for step_id in step_ids) <= 3
        assert all(len(step_id) <= 60 for step_id in step_ids)
        assert stored.state.get("repairLoopExit") == "reteach_then_revisit"


def test_prerequisite_gap_records_a_bounded_branch_trace(client):
    provider = FakeTutorProvider()
    with provider_context(provider):
        _, session = create_source_material(client)
        with SessionLocal() as db:
            stored = db.get(LearnSession, UUID(session["id"]))
            plan = deepcopy(stored.plan)
            prerequisite = deepcopy(plan["objectives"][0])
            prerequisite["id"] = "objective-height-prerequisite"
            prerequisite["title"] = "Height and potential energy"
            plan["objectives"][0]["prerequisiteIds"] = [prerequisite["id"]]
            plan["objectives"].append(prerequisite)
            state = deepcopy(stored.state)
            prerequisite_state = deepcopy(state["concepts"][0])
            prerequisite_state.update({"conceptId": prerequisite["id"], "title": prerequisite["title"], "state": "NOT_SEEN", "attempts": 0, "incorrect": 0})
            state["concepts"].append(prerequisite_state)
            stored.plan = plan
            stored.state = state
            db.commit()
        trace = TutorScenarioTrace("prerequisite_gap_branch")
        session = run_turn(client, trace, session, {})
        session = run_turn(client, trace, session, response_for(session.get("step"), text="I do not understand height."))
        session = run_turn(client, trace, session, response_for(session.get("step"), text="I still do not understand height."))
    assert_trace_invariants(trace)
    assert trace.turns[-1].session_state.get("prerequisiteBranch")
    assert len(trace.turns[-1].session_state.get("branchStack", [])) == 1


def test_fifty_replans_keep_runtime_and_persistence_bounded(client):
    provider = FakeTutorProvider()
    with provider_context(provider):
        _, session = create_source_material(client)
        trace = TutorScenarioTrace("fifty_replans")
        for _ in range(50):
            session = run_turn(client, trace, session, response_for(session.get("step"), text="confidently wrong"))
    assert len(trace.turns) == 50
    assert_trace_invariants(trace)
    with SessionLocal() as db:
        stored = db.get(LearnSession, session["id"])
        raw_state = json.dumps(stored.state)
        steps = stored.plan["objectives"][0]["steps"]
        # Three authored solve steps plus at most three bounded remediation
        # steps; the plan does not grow with the number of replans.
        assert len(steps) <= 6
        assert len(raw_state) < 25_000
        assert len(stored.state.get("branchStack", [])) <= 4
    fetched = client.get(f"/learn-sessions/{session['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == session["id"]


def test_generated_action_id_is_stable_bounded_and_keeps_step_identity():
    step = ShortAnswerStep(id="source-step-" + "x" * 48, type="short_answer", title="Explain energy", prompt="Why does speed increase?", acceptedAnswers=["potential energy becomes kinetic energy"], sourceSectionIds=["s1"], sourceBlockIds=["b1"])
    objective = {"id": "objective-" + "y" * 45, "title": "Energy"}
    concept = {"state": "DEVELOPING", "interactionTypes": []}
    first = _action_for(step, objective, concept)
    second = _action_for(step, objective, concept)
    assert first.id == second.id
    assert len(first.id) <= 60
    assert first.step_id == step.id
    assert step.id not in first.id


def test_remediation_identity_does_not_derive_from_previous_repair():
    step = ShortAnswerStep(id="original-check", type="short_answer", title="Explain energy", prompt="Why does speed increase?", acceptedAnswers=["potential becomes kinetic"], sourceSectionIds=["s1"], sourceBlockIds=["b1"])
    session = LearnSession(plan={"objectives": [{"id": "energy", "title": "Energy", "steps": [step.model_dump(by_alias=True)]}]}, state={})
    current = step
    generated = []
    for _ in range(3):
        index = _append_remediation(session, session.plan["objectives"][0], current)
        assert index is not None
        current = _parse_step(session.plan["objectives"][0]["steps"][index])
        generated.append(current.id)
    assert _append_remediation(session, session.plan["objectives"][0], current) is None
    assert len(set(generated)) == 3
    assert all(len(step_id) <= 60 for step_id in generated)
    assert all(not re.search(r"repair-.+repair-", step_id) for step_id in generated)


def test_scaffold_evidence_distinguishes_assisted_independent_and_transfer_success():
    assert next_scaffold("FULL", "correct", hints=2, independent=False) == "FULL"
    assert next_scaffold("FULL", "correct", hints=0, independent=True) == "GUIDED"
    assert next_scaffold("GUIDED", "correct", hints=0, independent=True) == "PARTIAL"
    assert next_scaffold("PARTIAL", "correct", hints=0, independent=True) == "INDEPENDENT"
    assert next_scaffold("INDEPENDENT", "correct", hints=0, independent=True) == "TRANSFER"


def test_correct_with_heavy_scaffolding_records_weaker_evidence_trace(client):
    provider = FakeTutorProvider()
    with provider_context(provider):
        _, session = create_source_material(client)
        trace = TutorScenarioTrace("correct_with_heavy_scaffolding")
        session = run_turn(client, trace, session, {})
        assert client.post(f"/learn-sessions/{session['id']}/hints", json={}).status_code == 200
        session = run_turn(client, trace, session, {"response": "independent correct"})
    assert_trace_invariants(trace)
    evidence = trace.turns[-1].evidence_update[0]
    assert evidence["state"] == "DEVELOPING"
    assert evidence["scaffold"] == "FULL"
    assert evidence["hintsUsed"] == 1


def test_independent_then_transfer_success_reduces_scaffolding(client):
    provider = FakeTutorProvider()
    with provider_context(provider):
        _, session = create_source_material(client)
        trace = TutorScenarioTrace("independent_and_transfer_success")
        session = run_turn(client, trace, session, {})
        session = run_turn(client, trace, session, {"response": "independent correct"})
        first_scaffold = trace.turns[-1].evidence_update[0]["scaffold"]
        if session.get("status") == "active" and session.get("step"):
            session = run_turn(client, trace, session, {"response": "transfer success"})
    assert_trace_invariants(trace)
    assert first_scaffold == "GUIDED"
    final = trace.turns[-1].evidence_update[0]
    assert final["scaffold"] in {"PARTIAL", "INDEPENDENT", "TRANSFER"}
    assert final["applicationEvidence"] >= 1


def test_long_source_ids_generate_bounded_grounded_plan_ids():
    source_id = "source-" + "very-long-identifier-" * 8
    plan = build_learn_plan({"sectionNotes": [{"id": source_id, "title": "Energy conversion", "bigIdea": "Potential energy becomes kinetic energy as the pendulum falls.", "sourceBlockIds": ["b1"], "keyTakeaways": ["Speed is greatest at the bottom."], "components": []}]}, "understand", "new")
    assert all(len(objective.id) <= 60 and all(len(step.id) <= 60 for step in objective.steps) for objective in plan.objectives)
    assert all(not student_facing_quality_issues(step) for objective in plan.objectives for step in objective.steps)


def test_ask_lucent_interrupt_uses_session_replan_state(client):
    provider = FakeTutorProvider()
    with provider_context(provider):
        _, session = create_source_material(client)
        response = client.post(f"/learn-sessions/{session['id']}/ask", json={"message": "Why is kinetic energy greatest at the bottom?"})
    assert response.status_code == 200
    assert response.json()["scope"] != "OUT_OF_SCOPE"
    assert "ask_lucent" in provider.calls and "learn_tutor_decision" in provider.calls
    with SessionLocal() as db:
        stored = db.get(LearnSession, session["id"])
        assert stored.state["lastTutorDecision"]["targetConcept"]
        before = next(item for item in stored.state["concepts"] if item["conceptId"] == stored.state["lastTutorDecision"]["targetConcept"])
        # Chat records uncertainty/replanning context but cannot directly add
        # graded evidence; only submit_learn_response may do so.
        assert before["attempts"] == 0


def test_unsafe_tool_and_meta_content_invariants_are_rejected():
    step = ShortAnswerStep(id="safe", type="short_answer", title="Energy", prompt="Which response best matches the teaching point?", acceptedAnswers=["the source-grounded relationship described above"], sourceSectionIds=["s1"], sourceBlockIds=["b1"])
    assert student_facing_quality_issues(step)
