from types import SimpleNamespace

from app.services.learn_runtime import apply_scene_message, apply_visual_event, build_tutor_observation, completion_met, ensure_runtime_state, process_tutor_event, push_prerequisite_branch, return_from_prerequisite, select_target_objective, _legacy_scene
from app.schemas.learn import ConceptEvidence
from app.routers.learn import _initial_state


def _session():
    objective = {
        "id": "energy",
        "title": "Energy conversion",
        "outcome": "Explain energy conversion.",
        "steps": [
            {"id": "teach", "type": "teach", "title": "Energy", "content": "Potential energy can become kinetic energy."},
            {"id": "check", "type": "multiple_choice", "title": "Check", "prompt": "Where is speed greatest?", "options": [{"id": "a", "label": "Turning point"}, {"id": "b", "label": "Bottom"}], "answerId": "b"},
        ],
    }
    return SimpleNamespace(id="session-1", plan={"objectives": [objective]}, state={}, objective_index=0, step_index=0, status="active", goal="understand")


def test_new_session_state_does_not_inherit_prior_evidence():
    state = _initial_state(None, None, 1, {"objectives": [{"id": "energy", "title": "Energy"}]})
    assert state["concepts"][0]["attempts"] == 0
    assert state["concepts"][0]["state"] == "NOT_SEEN"


def test_runtime_composes_teaching_and_practice_and_updates_evidence():
    session = _session()
    session.report = None
    session.ended_reason = None
    session.document_id = 1
    session.familiarity = "new"
    scene, private = process_tutor_event(session, {"id": "start", "type": "CONTINUE"})
    assert private and scene.response_interaction_id == "check"
    assert [block.kind for block in scene.blocks].count("practice") == 1
    scene, _ = process_tutor_event(session, {"id": "answer", "type": "RESPONSE", "interactionId": "check", "response": {"optionId": "a"}})
    assert session.state["concepts"][0]["incorrect"] == 1
    assert session.state["concepts"][0]["reviewDue"] == "LATER_THIS_SESSION"
    assert scene.revision > 1


def test_failed_response_teaches_before_exposing_another_assessment():
    session = _session()
    scene, _ = process_tutor_event(session, {"id": "start", "type": "CONTINUE"})
    scene, private = process_tutor_event(session, {"id": "wrong", "type": "RESPONSE", "interactionId": scene.response_interaction_id, "response": {"optionId": "a"}})
    assert scene.response_interaction_id is None
    assert any(block.kind == "explanation" for block in scene.blocks)
    assert private is None
    next_scene, next_private = process_tutor_event(session, {"id": "continue", "type": "CONTINUE"})
    assert next_private is not None
    assert next_scene.response_interaction_id is not None
    assert next_scene.response_interaction_id != "check"


def test_failed_response_remediation_scene_includes_learner_feedback():
    session = _session()
    scene, _ = process_tutor_event(session, {"id": "start", "type": "CONTINUE"})
    scene, _ = process_tutor_event(session, {"id": "wrong", "type": "RESPONSE", "interactionId": scene.response_interaction_id, "response": {"optionId": "a"}})
    feedback = [block for block in scene.blocks if block.kind == "feedback"]
    assert feedback, "a remediation response must visibly acknowledge the learner's error"
    assert feedback[0].content


def test_failed_response_advances_grounded_visual_for_followup():
    session = _session()
    session.plan["objectives"][0]["steps"][0]["visualSpec"] = {
        "type": "process_flow", "title": "Energy flow", "purpose": "See the conversion.",
        "nodes": [{"id": "top", "label": "Top"}, {"id": "bottom", "label": "Bottom"}],
        "edges": [{"source": "top", "target": "bottom", "label": "PE to KE"}],
        "stages": [{"title": "Top", "explanation": "PE is high.", "activeNodeIds": ["top"]}, {"title": "Bottom", "explanation": "KE is high.", "activeNodeIds": ["bottom"]}],
    }
    scene, _ = process_tutor_event(session, {"id": "start", "type": "CONTINUE"})
    assert scene.visual_state.stage == 0
    scene, _ = process_tutor_event(session, {"id": "wrong", "type": "RESPONSE", "interactionId": scene.response_interaction_id, "response": {"optionId": "a"}})
    assert scene.visual_state.stage == 1
    assert scene.visual_state.highlighted_element_ids == ["bottom"]
    assert any("highlighted" in (block.content or "") for block in scene.blocks if block.kind == "explanation")
    assert "visualState" not in session.state
    stage = scene.visual_state.stage
    continued, _ = process_tutor_event(session, {"id": "continue", "type": "CONTINUE"})
    assert continued.visual_state.stage == stage


def test_explicit_uncertainty_is_not_graded_as_correct_or_advanced():
    session = _session()
    scene, _ = process_tutor_event(session, {"id": "start", "type": "CONTINUE"})
    # The first active interaction is the authored matching check.
    scene, _ = process_tutor_event(session, {"id": "wrong", "type": "RESPONSE", "interactionId": scene.response_interaction_id, "response": {"optionId": "a"}})
    scene, private = process_tutor_event(session, {"id": "idk", "type": "CONTINUE"})
    scene, private = process_tutor_event(session, {"id": "uncertain", "type": "RESPONSE", "interactionId": scene.response_interaction_id, "response": {"response": "I don't know"}})
    assert private is None
    assert scene.objective_id == "energy"
    assert any(block.kind == "explanation" for block in scene.blocks)
    assert session.state["concepts"][0].get("uncertaintyCount", 0) == 1


def test_idk_produces_teaching_support_before_followup_practice():
    session = _session()
    scene, _ = process_tutor_event(session, {"id": "start", "type": "CONTINUE"})
    # First miss creates the teaching turn; Continue exposes the guided check.
    scene, _ = process_tutor_event(session, {"id": "wrong", "type": "RESPONSE", "interactionId": scene.response_interaction_id, "response": {"optionId": "a"}})
    scene, _ = process_tutor_event(session, {"id": "continue", "type": "CONTINUE"})
    active = scene.response_interaction_id
    scene, private = process_tutor_event(session, {"id": "idk", "type": "RESPONSE", "interactionId": active, "response": {"response": "I don't know"}})
    assert private is None
    assert any(block.kind == "explanation" and block.content for block in scene.blocks)
    assert scene.response_interaction_id is None
    followup, followup_private = process_tutor_event(session, {"id": "guided", "type": "CONTINUE"})
    assert followup_private is not None
    assert followup.response_interaction_id != active


def test_legacy_session_backfill_creates_runtime_v2_scene_idempotently():
    session = _session()
    scene, private = ensure_runtime_state(session)
    assert session.state["runtimeVersion"] == 2
    assert session.state["currentScene"]["id"] == scene.id
    # Teaching-only scenes intentionally have no active response payload.
    assert private is None
    again, again_private = ensure_runtime_state(session)
    assert again.revision == scene.revision
    assert again_private == private


def test_correct_response_does_not_represent_same_unanswered_interaction():
    session = _session()
    scene, _ = process_tutor_event(session, {"id": "start", "type": "CONTINUE"})
    scene, _ = process_tutor_event(session, {"id": "wrong", "type": "RESPONSE", "interactionId": "check", "response": {"optionId": "a"}})
    before = scene.revision
    current_id = scene.response_interaction_id
    scene, _ = process_tutor_event(session, {"id": "right", "type": "RESPONSE", "interactionId": current_id, "response": {"optionId": "b"}})
    assert scene.revision > before
    assert scene.response_interaction_id != "check"
    assert not any(block.kind == "practice" and block.step and block.step.id == "check" for block in scene.blocks)


def test_runtime_ids_and_revisions_remain_bounded_across_replans():
    session = _session()
    process_tutor_event(session, {"id": "start", "type": "CONTINUE"})
    for index in range(50):
        process_tutor_event(session, {"id": f"answer-{index}", "type": "RESPONSE", "interactionId": "check", "response": {"optionId": "a"}})
    assert len(session.state["sceneHistory"]) <= 8
    assert len(session.state["currentScene"]["id"]) <= 60
    if session.state.get("currentScenePrivate"):
        assert len(session.state["currentScenePrivate"]["decisionId"]) <= 60


def test_candidate_exhaustion_generates_bounded_grounded_followup_without_plan_mutation():
    session = _session()
    original_steps = list(session.plan["objectives"][0]["steps"])
    process_tutor_event(session, {"id": "start", "type": "CONTINUE"})
    process_tutor_event(session, {"id": "wrong", "type": "RESPONSE", "interactionId": "check", "response": {"optionId": "a"}})
    process_tutor_event(session, {"id": "continue", "type": "CONTINUE"})
    # The authored plan remains immutable while an in-memory follow-up is
    # exposed as the next practice surface.
    assert session.plan["objectives"][0]["steps"] == original_steps
    private = session.state["currentScenePrivate"]
    assert private and private["interaction"]["id"].startswith("repair-")
    assert len(private["interaction"]["id"]) <= 60


def test_ask_message_mutates_authoritative_scene_and_visual_state():
    session = _session()
    process_tutor_event(session, {"id": "start", "type": "CONTINUE"})
    scene = apply_scene_message(session, message="Show me visually", answer="Watch the conversion at the bottom.", source_section_ids=["s1"], visual_action={"stage": 2, "nodeId": "bottom"})
    assert scene and scene.visual_state.stage == 2
    assert any(block.label == "Ask Lucent" for block in scene.blocks)
    assert session.state["currentScene"]["visualState"]["stage"] == 2


def test_ask_event_uses_authoritative_runtime_scene_executor():
    session = _session()
    process_tutor_event(session, {"id": "start", "type": "CONTINUE"})
    before = session.state["currentScene"]["revision"]
    scene, private = process_tutor_event(session, {
        "id": "ask-1", "type": "ASK_LUCENT", "message": "Explain this another way",
        "answer": "Potential energy can become kinetic energy as the pendulum falls.",
        "sourceSectionIds": ["s1"], "sourceBlockIds": ["b1"],
        "blockKind": "explanation", "blockLabel": "Another way",
    })
    assert scene.revision > before
    assert any(block.kind == "explanation" and block.content for block in scene.blocks)
    assert private is not None


def test_ask_event_replacement_step_is_executed_by_runtime():
    session = _session()
    process_tutor_event(session, {"id": "start", "type": "CONTINUE"})
    replacement = {"id": "ask-replacement", "type": "multiple_choice", "title": "Explain the relationship", "prompt": "Where does energy go as the pendulum falls?", "options": [{"id": "a", "label": "Into motion"}, {"id": "b", "label": "It disappears"}], "answerId": "a", "sourceSectionIds": [], "sourceBlockIds": []}
    scene, private = process_tutor_event(session, {"id": "ask", "type": "ASK_LUCENT", "message": "Ask me another question", "answer": "Let's try a new check.", "replacementStep": replacement})
    assert scene.response_interaction_id == "ask-replacement"
    assert private and private["interaction"]["id"] == "ask-replacement"
    assert any(block.kind == "practice" and block.step and block.step.id == "ask-replacement" for block in scene.blocks)


def test_ask_message_can_add_grounded_visual_reference_to_teaching_only_scene():
    session = _session()
    process_tutor_event(session, {"id": "start", "type": "CONTINUE"})
    scene = apply_scene_message(
        session,
        message="Show me visually",
        answer="Watch the conversion at the bottom.",
        source_section_ids=["s1"],
        source_block_ids=["b1"],
        visual_action={"stage": 0, "visualRef": {"sectionId": "s1", "componentIndex": 0}},
    )
    assert scene is not None
    visual_blocks = [block for block in scene.blocks if block.kind == "visual"]
    assert visual_blocks and visual_blocks[0].visual_ref == {"sectionId": "s1", "componentIndex": 0}


def test_visual_event_persists_canonical_stage_and_highlight():
    session = _session()
    process_tutor_event(session, {"id": "start", "type": "CONTINUE"})
    scene = apply_visual_event(session, event="set_stage", stage=1)
    assert scene is not None
    assert scene.revision > 1
    assert session.state["currentScene"]["visualState"]["stage"] == 1


def test_scene_normalizes_legacy_mental_model_heading():
    session = _session()
    session.plan["objectives"][0]["steps"][0]["title"] = "Build the mental model"
    scene, _ = process_tutor_event(session, {"id": "start", "type": "CONTINUE"})
    titles = [block.title for block in scene.blocks if block.title]
    assert "Build the mental model" not in titles


def test_concept_evidence_accepts_semantic_scaffold_and_legacy_numeric_value():
    base = {"conceptId": "energy", "title": "Energy", "state": "DEVELOPING", "scaffoldingLevel": "FULL", "scaffold": "FULL"}
    assert ConceptEvidence.model_validate(base).scaffolding_level == "FULL"
    assert ConceptEvidence.model_validate({**base, "scaffoldingLevel": 3}).scaffolding_level == "INDEPENDENT"


def test_session_payload_serializes_runtime_semantic_scaffold():
    import os
    os.environ.setdefault("DATABASE_URL", "sqlite:///tmp.db")
    from app.routers.learn import _session_payload
    session = _session()
    session.report = None
    session.ended_reason = None
    session.document_id = 1
    session.familiarity = "new"
    session.state = {"concepts": [{"conceptId": "energy", "title": "Energy", "state": "DEVELOPING", "scaffoldingLevel": "FULL", "scaffold": "FULL"}]}
    payload = _session_payload(session)
    assert payload.concept_states[0].scaffolding_level == "FULL"


def test_generated_followup_can_be_answered_and_graded_correctly():
    # Regression: _private_for_rendered_scene used to persist the public
    # LearnStepView (which has no answer fields) as the graded interaction
    # whenever a practice block already existed in the rendered scene -- which
    # is always. A generated repair question could therefore never be graded
    # correctly, so it kept regenerating instead of ever advancing evidence.
    session = _session()
    process_tutor_event(session, {"id": "start", "type": "CONTINUE"})
    process_tutor_event(session, {"id": "wrong", "type": "RESPONSE", "interactionId": "check", "response": {"optionId": "a"}})
    scene, private = process_tutor_event(session, {"id": "continue", "type": "CONTINUE"})
    assert private and private["interaction"]["id"].startswith("repair-")
    assert private["interaction"].get("acceptedAnswers"), "private interaction lost its answer-bearing fields"
    followup_id = private["interaction"]["id"]
    accepted_answer = private["interaction"]["acceptedAnswers"][0]
    process_tutor_event(session, {"id": "answer-followup", "type": "RESPONSE", "interactionId": followup_id, "response": {"response": accepted_answer}})
    concept = session.state["concepts"][0]
    assert concept["correct"] >= 1
    assert followup_id in session.state["answeredInteractionIds"]


def test_exhausted_objective_advances_to_next_unmastered_objective():
    # Regression: once an objective's candidates were exhausted, the runtime
    # persisted the same inert (no-practice) scene forever -- Continue bumped
    # the revision but never reached the next objective. Exhaustion is
    # reached the way a real learner would: keep answering incorrectly,
    # never by mashing Continue on an already-active, unanswered practice.
    session = _session()
    session.plan["objectives"].append({
        "id": "second", "title": "Second objective", "outcome": "Explain the second idea.",
        "steps": [{"id": "second-teach", "type": "teach", "title": "Second", "content": "Second idea content."}],
    })
    scene, _ = process_tutor_event(session, {"id": "start", "type": "CONTINUE"})
    for index in range(8):
        if scene.objective_id != "energy":
            break
        interaction_id = scene.response_interaction_id
        scene, _ = process_tutor_event(session, {"id": f"wrong-{index}", "type": "RESPONSE", "interactionId": interaction_id, "response": {"response": "definitely not the source-supported idea", "optionId": "a"}})
    assert scene.objective_id == "second"
    assert session.state["currentObjectiveId"] == "second"


def test_exhausted_single_objective_session_stays_active_for_evidence_review():
    session = _session()
    session.report = None
    session.ended_reason = None
    scene, _ = process_tutor_event(session, {"id": "start", "type": "CONTINUE"})
    for index in range(8):
        if session.status == "completed":
            break
        interaction_id = scene.response_interaction_id
        scene, _ = process_tutor_event(session, {"id": f"wrong-{index}", "type": "RESPONSE", "interactionId": interaction_id, "response": {"response": "definitely not the source-supported idea", "optionId": "a"}})
    assert session.status == "active"
    assert scene.response_interaction_id is not None or session.state.get("revisitQueue")


def test_two_exhausted_objectives_complete_instead_of_oscillating():
    # Regression: selecting "any objective that is not DEMONSTRATED" as the
    # transition target ignored whether that objective itself still had any
    # candidates left. Two exhausted objectives bounced the learner back and
    # forth between them forever (observed live: 10+ consecutive alternations
    # with no progress) instead of ever completing the session.
    session = _session()
    session.report = None
    session.ended_reason = None
    session.plan["objectives"].append({
        "id": "second", "title": "Second objective", "outcome": "Explain the second idea.",
        "steps": [{"id": "second-teach", "type": "teach", "title": "Second", "content": "Second idea content."}],
    })
    scene, _ = process_tutor_event(session, {"id": "start", "type": "CONTINUE"})
    seen_objectives = []
    for index in range(16):
        if session.status == "completed":
            break
        seen_objectives.append(scene.objective_id)
        interaction_id = scene.response_interaction_id
        if interaction_id:
            scene, _ = process_tutor_event(session, {"id": f"wrong-{index}", "type": "RESPONSE", "interactionId": interaction_id, "response": {"response": "definitely not the source-supported idea", "optionId": "a"}})
        else:
            scene, _ = process_tutor_event(session, {"id": f"continue-{index}", "type": "CONTINUE"})
    assert session.status == "completed", f"session never completed; objective sequence was {seen_objectives}"
    # Revisit is allowed once for delayed review, but it must be bounded and
    # never bounce indefinitely between exhausted objectives.
    from collections import Counter
    runs = [key for key, _ in __import__("itertools").groupby(seen_objectives)]
    counts = Counter(runs)
    assert all(count <= 2 for count in counts.values()), f"unbounded objective revisit: {seen_objectives}"


def test_due_exhausted_concept_is_revisited_with_new_retrieval_interaction():
    session = _session()
    session.plan["objectives"].append({
        "id": "second", "title": "Second objective", "outcome": "Explain the second idea.",
        "steps": [{"id": "second-check", "type": "multiple_choice", "title": "Second check", "prompt": "Which statement is supported?", "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}], "answerId": "b"}],
    })
    ensure_runtime_state(session)
    state = session.state
    state["revisitQueue"] = ["energy"]
    state["answeredInteractionIds"] = ["teach", "check"]
    state["revisitMode"] = True
    state["concepts"] = [{"conceptId": "energy", "state": "DEVELOPING", "reviewVisits": 0}]
    assert select_target_objective(session, exclude_concept_id="second") == "energy"
    session.state["revisitQueue"] = ["energy"]
    session.state["concepts"][0]["reviewVisits"] = 0
    scene, private = _legacy_scene(session, session.plan["objectives"][0])
    assert private and private["interaction"]["id"].startswith("review-")
    assert scene.response_interaction_id != "check"


def test_revisit_waits_for_intervening_objective_before_returning():
    """A queued weak concept is reviewed after another objective gets a turn."""
    session = _session()
    session.plan["objectives"].append({
        "id": "second", "title": "Second objective", "outcome": "Explain the second idea.",
        "steps": [{"id": "second-check", "type": "multiple_choice", "title": "Second check", "prompt": "Which statement is supported?", "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}], "answerId": "b"}],
    })
    ensure_runtime_state(session)
    state = session.state
    state["revisitQueue"] = ["energy"]
    state["concepts"] = [
        {"conceptId": "energy", "state": "NEEDS_REVIEW", "reviewVisits": 0},
        {"conceptId": "second", "state": "NOT_SEEN", "reviewVisits": 0},
    ]
    # New material is the intervening turn; only after it is exhausted does
    # the queued concept become the next target.
    assert select_target_objective(session) == "second"
    state["answeredInteractionIds"] = ["second-check"]
    assert select_target_objective(session) == "energy"


def test_exhausted_authored_assets_never_resurrect_first_interaction():
    session = _session()
    ensure_runtime_state(session)
    session.state["answeredInteractionIds"] = ["teach", "check"]
    session.state["usedTeachingIds"] = ["teach"]
    scene, private = _legacy_scene(session, session.plan["objectives"][0])
    assert private is not None
    assert private["interaction"]["id"] != "check"
    assert private["interaction"]["id"].startswith("autonomous-")


def test_attempt_history_prevents_reselecting_interaction_when_state_list_is_stale():
    session = _session()
    ensure_runtime_state(session)
    session.state["answeredInteractionIds"] = ["teach"]
    session.state["usedTeachingIds"] = ["teach"]
    # This mirrors the old write ordering bug: the attempt row is durable,
    # while the JSON compatibility list has not yet caught up.
    session.attempts = [SimpleNamespace(step_id="check")]
    scene, private = _legacy_scene(session, session.plan["objectives"][0])
    assert private is not None
    assert private["interaction"]["id"] != "check"


def test_matching_failure_gets_a_contrastive_remediation_not_a_generic_prompt():
    # A wrong structured (matching/multiple_choice/prediction/ordering/
    # labeling) answer should get a targeted contrast built from what the
    # learner actually got wrong, not the generic "explain the main idea"
    # short-answer prompt every objective otherwise falls back to.
    objective = {
        "id": "genetics", "title": "Opposing mutation mechanisms",
        "outcome": "Explain how proto-oncogenes and tumor suppressors differ.",
        "steps": [
            {
                "id": "match", "type": "matching", "title": "Match the mechanisms",
                "prompt": "Match each pathway to its mutation type.",
                "pairs": [{"id": "oncogene", "label": "Proto-oncogene"}, {"id": "suppressor", "label": "Tumor suppressor"}],
                "matches": {"oncogene": "Gain-of-function", "suppressor": "Loss-of-function"},
                "sourceSectionIds": ["genetics"], "sourceBlockIds": ["block-1"],
            },
        ],
    }
    session = SimpleNamespace(id="session-2", plan={"objectives": [objective]}, state={}, objective_index=0, step_index=0, status="active", goal="understand")
    scene, private = process_tutor_event(session, {"id": "start", "type": "CONTINUE"})
    assert scene.response_interaction_id == "match"
    scene, private = process_tutor_event(session, {"id": "wrong", "type": "RESPONSE", "interactionId": "match", "response": {"response": "{}"}})
    # A miss first produces a teaching-only contrast; it must not immediately
    # expose another assessment before the learner sees the correction.
    assert private is None
    assert any(block.kind == "explanation" for block in scene.blocks)
    scene, private = process_tutor_event(session, {"id": "continue", "type": "CONTINUE"})
    assert private is not None
    interaction = private["interaction"]
    assert interaction["type"] in {"multiple_choice", "short_answer"}
    text = str(interaction).casefold()
    assert "gain-of-function" in text and "loss-of-function" in text
    assert "proto-oncogene" in text and "tumor suppressor" in text


def test_prerequisite_branch_is_bounded_and_returns_to_original_objective():
    session = _session()
    session.plan["objectives"].append({"id": "prereq", "title": "Prerequisite", "outcome": "Know the prerequisite", "steps": [{"id": "p", "type": "teach", "title": "Prerequisite", "content": "A prerequisite idea."}]})
    branch = push_prerequisite_branch(session, original_concept_id="energy", prerequisite_concept_id="prereq", reason="The prerequisite is not demonstrated.", return_scene_id="scene-1")
    assert branch and session.state["currentObjectiveId"] == "prereq"
    assert return_from_prerequisite(session)["returnObjectiveId"] == "energy"


def test_prerequisite_branch_runtime_teaches_repairs_and_returns():
    session = _session()
    session.plan["objectives"][0]["prerequisiteIds"] = ["prereq"]
    session.plan["objectives"].append({
        "id": "prereq",
        "title": "Height and potential energy",
        "outcome": "Height determines gravitational potential energy.",
        "steps": [
            {"id": "p-teach", "type": "teach", "title": "Build the prerequisite", "content": "Greater height means greater gravitational potential energy."},
            {"id": "p-check", "type": "short_answer", "title": "Check the prerequisite", "prompt": "What does greater height change?", "acceptedAnswers": ["potential energy"], "sourceSectionIds": ["s"], "sourceBlockIds": ["b"]},
        ],
    })
    scene, _ = process_tutor_event(session, {"id": "start", "type": "CONTINUE"})
    scene, private = process_tutor_event(session, {"id": "continue", "type": "CONTINUE"})
    assert private and scene.response_interaction_id == "check"
    scene, private = process_tutor_event(session, {"id": "wrong", "type": "RESPONSE", "interactionId": "check", "response": {"optionId": "a"}})
    assert private and session.state["currentObjectiveId"] == "prereq"
    scene, private = process_tutor_event(session, {"id": "continue-prereq", "type": "CONTINUE"})
    assert private and private["interaction"]["id"] == "p-check"
    scene, private = process_tutor_event(session, {"id": "prereq-answer", "type": "RESPONSE", "interactionId": "p-check", "response": {"response": "potential energy"}})
    assert session.state["currentObjectiveId"] == "energy"
    assert not session.state.get("branchStack")
    assert private and private["objectiveId"] == "energy"
    assert scene.objective_id == "energy"


def test_prerequisite_branch_cycle_guard_uses_canonical_key():
    session = _session()
    session.plan["objectives"].append({"id": "prereq", "title": "Prerequisite", "outcome": "Know the prerequisite", "steps": []})
    session.state = {"branchStack": [{"prerequisiteConceptId": "prereq"}]}
    from app.services.learn_runtime import validate_branch_proposal
    assert not validate_branch_proposal(session, original_concept_id="energy", prerequisite_concept_id="prereq", depth=2)


def test_tutor_observation_carries_evidence_history_and_visual_state():
    session = _session()
    scene, _ = process_tutor_event(session, {"id": "start", "type": "CONTINUE"})
    state = session.state
    concept = state["concepts"][0]
    concept.update({"recognitionEvidence": 2, "recallEvidence": 1, "explanationEvidence": 1, "applicationEvidence": 1, "transferEvidence": 0, "scaffoldingLevel": "GUIDED", "uncertaintyCount": 1})
    state["answeredInteractionIds"] = ["old-check"]
    state["usedTeachingIds"] = ["teach"]
    session.state = state
    observation = build_tutor_observation(session)
    assert observation.evidence["applicationEvidence"] == 1
    assert observation.evidence["transferEvidence"] == 0
    assert observation.evidence["scaffoldingLevel"] == "GUIDED"
    assert observation.evidence["answeredInteractionIds"] == ["old-check"]
    assert observation.evidence["sceneRevision"] == scene.revision


def test_application_success_composes_transfer_before_objective_completion():
    objective = {
        "id": "motion", "title": "Force and motion",
        "outcome": "Force equals mass times acceleration.",
        "steps": [{"id": "solve", "type": "problem", "title": "Solve", "prompt": "What is force?", "acceptedAnswers": ["10"], "sourceSectionIds": ["s"], "sourceBlockIds": ["b"]}],
    }
    session = SimpleNamespace(id="transfer-session", plan={"objectives": [objective]}, state={}, objective_index=0, step_index=0, status="active", goal="understand")
    scene, _ = process_tutor_event(session, {"id": "start", "type": "CONTINUE"})
    scene, private = process_tutor_event(session, {"id": "answer", "type": "RESPONSE", "interactionId": scene.response_interaction_id, "response": {"response": "10"}})
    assert session.status == "active"
    assert private and private["interaction"]["type"] == "teach_back"
    # Guided/application success earns an independent check before transfer;
    # transfer is only composed after that stronger evidence is collected.
    assert private["interaction"]["id"].startswith("independent-")
    assert scene.response_interaction_id != "solve"
    assert "concrete situation" in private["interaction"]["prompt"]
    scene, private = process_tutor_event(session, {"id": "independent-answer", "type": "RESPONSE", "interactionId": scene.response_interaction_id, "response": {"response": "Force equals mass times acceleration in a concrete situation."}})
    assert session.status == "active"
    assert private and private["interaction"]["id"].startswith("transfer-")
    assert "new situation" in private["interaction"]["prompt"]
