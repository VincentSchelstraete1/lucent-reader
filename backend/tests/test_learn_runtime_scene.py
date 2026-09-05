from types import SimpleNamespace

from app.services.learn_runtime import process_tutor_event


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


def test_runtime_composes_teaching_and_practice_and_updates_evidence():
    session = _session()
    scene, private = process_tutor_event(session, {"id": "start", "type": "CONTINUE"})
    assert private and scene.response_interaction_id == "check"
    assert [block.kind for block in scene.blocks].count("practice") == 1
    scene, _ = process_tutor_event(session, {"id": "answer", "type": "RESPONSE", "interactionId": "check", "response": {"optionId": "a"}})
    assert session.state["concepts"][0]["incorrect"] == 1
    assert session.state["concepts"][0]["reviewDue"] == "LATER_THIS_SESSION"
    assert scene.revision > 1


def test_runtime_ids_and_revisions_remain_bounded_across_replans():
    session = _session()
    process_tutor_event(session, {"id": "start", "type": "CONTINUE"})
    for index in range(50):
        process_tutor_event(session, {"id": f"answer-{index}", "type": "RESPONSE", "interactionId": "check", "response": {"optionId": "a"}})
    assert len(session.state["sceneHistory"]) <= 8
    assert len(session.state["currentScene"]["id"]) <= 60
    assert len(session.state["currentScenePrivate"]["decisionId"]) <= 60
