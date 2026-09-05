import pytest
from pydantic import ValidationError

from app.schemas.learn import LearningScene, MultipleChoiceStep, TeachStep, TutorAction, TutorDecision, TutorEvent, TutorScenePlan
from app.services.learn_scene import compose_learning_scene


def _scene(*, step_index=1, decision=None):
    teach = {
        "id": "teach-energy", "type": "teach", "title": "Energy changes",
        "content": "As the pendulum falls, gravitational potential energy becomes kinetic energy.",
        "sourceSectionIds": ["section-energy"], "sourceBlockIds": ["block-energy"],
    }
    check = MultipleChoiceStep(
        id="predict-speed", type="multiple_choice", title="Predict the speed",
        prompt="Where is the pendulum moving fastest?",
        options=[{"id": "bottom", "label": "At the bottom"}, {"id": "turn", "label": "At a turning point"}],
        answerId="bottom", sourceSectionIds=["section-energy"], sourceBlockIds=["block-energy"],
    ).model_dump(by_alias=True)
    objective = {"id": "energy-objective", "title": "Pendulum energy", "outcome": "Explain the energy change", "bottleneck": "Connect speed to kinetic energy", "sourceSectionIds": ["section-energy"], "sourceBlockIds": ["block-energy"]}
    action = TutorAction(id="action-check", type="ask_multiple_choice", conceptId="energy-objective", stepId="predict-speed", rationale="Check the relationship")
    return compose_learning_scene(
        session_id="session-1", objective=objective, steps=[teach, check], step_index=step_index,
        current_step=MultipleChoiceStep.model_validate(check), action=action, decision=decision,
        concept={"scaffold": "GUIDED"}, state={"sceneRevision": 2},
    )


def test_scene_coalesces_teaching_and_practice_with_one_response_target():
    scene = _scene()
    assert [block.kind for block in scene.blocks] == ["explanation", "practice"]
    assert scene.response_step_id == "predict-speed"
    assert sum(bool(block.step) for block in scene.blocks) == 1
    assert scene.source_block_ids == ["block-energy"]


def test_scene_plan_can_choose_a_different_grounded_candidate():
    decision = TutorDecision(
        targetConcept="energy-objective", teachingAction="ask_multiple_choice",
        pedagogicalGoal="VERIFY_UNDERSTANDING", pedagogicalStrategy="GUIDED_DISCOVERY",
        scenePlan=TutorScenePlan(blocks=[{"kind": "practice", "label": "Predict", "stepId": "predict-speed"}]),
    )
    scene = _scene(decision=decision)
    assert scene.response_step_id == "predict-speed"
    assert any(block.kind == "practice" for block in scene.blocks)


def test_scene_ids_and_size_are_bounded():
    scene = _scene()
    assert len(scene.id) <= 60
    assert len(scene.blocks) <= 6
    assert all(len(block.id) <= 60 for block in scene.blocks)


def test_scene_plan_keeps_ask_lucent_example_on_same_teaching_surface():
    decision = TutorDecision(
        targetConcept="energy-objective", teachingAction="give_example",
        pedagogicalGoal="BUILD_INTUITION", pedagogicalStrategy="CONCRETE_EXAMPLE",
        scenePlan=TutorScenePlan(blocks=[{
            "kind": "example", "label": "Example", "title": "Pendulum energy",
            "content": "As the pendulum falls, gravitational potential energy becomes kinetic energy.",
            "sourceSectionIds": ["section-energy"], "sourceBlockIds": ["block-energy"],
        }]),
    )
    scene = _scene(decision=decision)
    assert any(block.kind == "example" for block in scene.blocks)
    assert any(block.kind == "practice" for block in scene.blocks)
    assert scene.source_section_ids == ["section-energy"]


def test_teaching_scene_reuses_next_grounded_visual_before_practice():
    visual = {
        "type": "process_flow", "title": "Energy conversion", "purpose": "See energy move as the pendulum falls",
        "nodes": [{"id": "high", "label": "High point", "detail": "Potential energy is greatest."}, {"id": "low", "label": "Bottom", "detail": "Kinetic energy is greatest."}],
        "edges": [{"source": "high", "target": "low", "label": "falls"}],
        "stages": [{"title": "Fall", "explanation": "Potential energy becomes kinetic energy.", "activeNodeIds": ["high", "low"]}],
    }
    teach = {"id": "teach", "type": "teach", "title": "Energy changes", "content": "Potential energy becomes kinetic energy as the pendulum falls.", "sourceSectionIds": ["s"], "sourceBlockIds": ["b"]}
    visual_step = {"id": "visual", "type": "teach", "title": "Energy diagram", "content": "The diagram tracks the conversion.", "visualSpec": visual, "sourceSectionIds": ["s"], "sourceBlockIds": ["b"]}
    objective = {"id": "o", "title": "Pendulum energy", "outcome": "Explain energy conversion", "sourceSectionIds": ["s"], "sourceBlockIds": ["b"]}
    current = TeachStep.model_validate(teach)
    scene = compose_learning_scene(session_id="s", objective=objective, steps=[teach, visual_step], step_index=0, current_step=current, action=None, decision=None, concept={"scaffold": "FULL"}, state={})
    assert [block.kind for block in scene.blocks] == ["explanation", "visual"]
    assert scene.blocks[1].visual_spec is not None


def test_public_scene_excludes_internal_tutor_metadata_and_normalizes_legacy_response_id():
    scene = LearningScene.model_validate({
        "id": "scene-1", "revision": 1, "objectiveId": "o", "objective": "Energy",
        "blocks": [{"id": "b", "kind": "explanation", "label": "Understand", "content": "Energy changes.", "sourceSectionIds": ["s"], "sourceBlockIds": ["b"]}],
        "responseStepId": "legacy-check", "pedagogicalGoal": "VERIFY_UNDERSTANDING", "tutorHypothesis": "internal",
        "strategy": "DIRECT_INSTRUCTION", "scaffoldLevel": "FULL", "completionCondition": "internal",
    })
    payload = scene.model_dump(by_alias=True)
    assert payload["responseInteractionId"] == "legacy-check"
    assert "tutorHypothesis" not in payload
    assert "pedagogicalGoal" not in payload
    assert "strategy" not in payload
    assert "scaffoldLevel" not in payload


def test_tutor_event_rejects_missing_payload_and_unknown_fields():
    with pytest.raises(ValidationError):
        TutorEvent.model_validate({"id": "e", "type": "RESPONSE"})
    with pytest.raises(ValidationError):
        TutorEvent.model_validate({"id": "e", "type": "ASK_LUCENT", "message": "Explain", "unsafe": True})
