import pytest
from pydantic import ValidationError

from app.routers import step_through
from app.schemas.step_through import GeneratedStepThroughMechanism, StepThroughMechanism


def test_step_through_replay_is_valid_and_uses_zero_model_calls(client):
    response = client.post("/dev/step-through/generate", json={
        "fixture_name": "gram-schmidt",
        "source_text": "Gram-Schmidt starts with a set of vectors. Keep the first vector as the first basis direction. For each later vector, project it onto every earlier orthogonal direction, subtract those projections, and keep the remaining perpendicular component. Normalize the resulting vectors when an orthonormal basis is needed.",
        "mode": "replay",
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["metadata"]["model_call_count"] == 0
    assert body["metadata"]["cache_hit"] is True
    assert StepThroughMechanism.model_validate(body["mechanism"])


def test_step_through_unknown_replay_does_not_call_provider(client):
    response = client.post("/dev/step-through/generate", json={
        "fixture_name": "bubble-sort",
        "source_text": "A source with no recorded replay.",
        "mode": "replay",
    })
    assert response.status_code == 404


def test_sequence_exchange_visual_is_strict_and_semantic_only():
    payload = {
        "sceneType": "sequence_exchange_scene",
        "title": "Handshake",
        "learningGoal": "Understand the exchange",
        "entities": [{"id": "client", "label": "Client"}, {"id": "server", "label": "Server"}],
        "stages": [{
            "title": "SYN",
            "explanation": "The client initiates.",
            "visual": {
                "type": "sequence_exchange_scene",
                "actors": [{"id": "client", "label": "Client"}, {"id": "server", "label": "Server"}],
                "messages": [{"id": "syn", "sender": "client", "receiver": "server", "label": "SYN"}],
                "visibleMessageIds": ["syn"],
            },
        }, {"title": "Done", "explanation": "The exchange completes.", "visual": {
            "type": "sequence_exchange_scene",
            "actors": [{"id": "client", "label": "Client"}, {"id": "server", "label": "Server"}],
            "messages": [{"id": "syn", "sender": "client", "receiver": "server", "label": "SYN"}],
            "visibleMessageIds": ["syn"],
        }}],
        "conclusion": "The peers synchronize.",
    }
    mechanism = StepThroughMechanism.model_validate(payload)
    assert mechanism.stages[0].visual.type == "sequence_exchange_scene"
    payload["stages"][0]["visual"]["coordinates"] = {"x": 1}
    try:
        StepThroughMechanism.model_validate(payload)
    except Exception:
        pass
    else:
        raise AssertionError("presentation coordinates must be rejected")


def test_ordered_items_replays_for_bubble_and_insertion_sort(client):
    for fixture_name in ("bubble-sort", "insertion-sort"):
        source = {
            "bubble-sort": "Bubble sort repeatedly compares adjacent elements. If a pair is out of order, swap it. After one pass the largest remaining element bubbles to the end; repeat passes until no swaps are needed.",
            "insertion-sort": "Insertion sort grows a sorted prefix. Take the next item, compare it with items to its left, shift larger items right, and insert the item into its sorted position.",
        }[fixture_name]
        response = client.post("/dev/step-through/generate", json={"fixture_name": fixture_name, "source_text": source, "mode": "replay"})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["mechanism"]["sceneType"] == "ordered_items_scene"
        assert body["metadata"]["model_call_count"] == 0
        assert body["metadata"]["fixture_kind"] == "sample_manual"
        mechanism = StepThroughMechanism.model_validate(body["mechanism"])
        state_changing = [stage.visual for stage in mechanism.stages if stage.visual and stage.visual.type == "ordered_items_scene" and stage.visual.operation.type in {"swap", "move", "mark_complete"}]
        assert state_changing
        assert all(scene.after is not None for scene in state_changing)


def _valid_ordered_payload():
    return {
        "sceneType": "ordered_items_scene",
        "title": "Ordered transition",
        "learningGoal": "See why the collection changes",
        "entities": [
            {"id": "left", "kind": "item", "label": "7"},
            {"id": "right", "kind": "item", "label": "4"},
        ],
        "stages": [
            {
                "title": "Compare",
                "explanation": "Compare the values.",
                "visual": {
                    "type": "ordered_items_scene",
                    "before": {"items": [{"entityId": "left", "status": "compared"}, {"entityId": "right", "status": "compared"}]},
                    "operation": {"type": "compare", "entityIds": ["left", "right"], "reason": "7 is greater than 4."},
                },
            },
            {
                "title": "Swap",
                "explanation": "Put the smaller value first.",
                "visual": {
                    "type": "ordered_items_scene",
                    "before": {"items": [{"entityId": "left"}, {"entityId": "right"}]},
                    "operation": {"type": "swap", "entityIds": ["left", "right"], "reason": "Ascending order requires 4 first.", "result": "4 now precedes 7."},
                    "after": {"items": [{"entityId": "right", "status": "changed"}, {"entityId": "left", "status": "changed"}]},
                },
            },
        ],
        "conclusion": "The reason explains the state transition.",
    }


def test_visual_dsl_separates_ids_labels_and_validates_references():
    mechanism = StepThroughMechanism.model_validate(_valid_ordered_payload())
    assert mechanism.entities[0].id == "left"
    assert mechanism.entities[0].label == "7"

    invalid = _valid_ordered_payload()
    invalid["stages"][0]["visual"]["operation"]["entityIds"] = ["left", "missing"]
    with pytest.raises(ValidationError, match="operation entityIds"):
        StepThroughMechanism.model_validate(invalid)


def test_state_changing_ordered_operations_require_coherent_after_state():
    missing_after = _valid_ordered_payload()
    missing_after["stages"][1]["visual"].pop("after")
    with pytest.raises(ValidationError, match="requires an after state"):
        StepThroughMechanism.model_validate(missing_after)

    unchanged = _valid_ordered_payload()
    unchanged["stages"][1]["visual"]["after"]["items"] = [{"entityId": "left"}, {"entityId": "right"}]
    with pytest.raises(ValidationError, match="must change item order"):
        StepThroughMechanism.model_validate(unchanged)


def test_visual_dsl_rejects_presentation_fields_and_unsupported_language():
    payload = _valid_ordered_payload()
    payload["stages"][0]["visual"]["coordinates"] = {"x": 10, "y": 20}
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        StepThroughMechanism.model_validate(payload)

    payload = _valid_ordered_payload()
    payload["stages"][0]["visual"]["operation"]["type"] = "rotate"
    with pytest.raises(ValidationError, match="Input should be"):
        StepThroughMechanism.model_validate(payload)

    payload = _valid_ordered_payload()
    payload["sceneType"] = "cartesian_scene"
    with pytest.raises(ValidationError, match="Input should be"):
        StepThroughMechanism.model_validate(payload)

    payload = _valid_ordered_payload()
    payload["stages"][0]["visual"]["operation"]["reason"] = "<svg><path /></svg>"
    with pytest.raises(ValidationError, match="cannot contain raw SVG"):
        StepThroughMechanism.model_validate(payload)


def test_generation_schema_is_the_strict_visual_dsl_contract():
    schema = StepThroughMechanism.generation_schema()
    schema_text = str(schema)
    assert "ordered_items_scene" in schema_text
    assert "entityIds" in schema_text
    assert "reason" in schema_text
    assert "resultingOrder" in schema_text
    assert "visualProgram" in schema_text
    assert "coordinates" not in schema_text
    assert "color" not in schema["$defs"]["GeneratedStepEntity"]["properties"]
    assert "stateChanges" not in schema_text
    assert schema == GeneratedStepThroughMechanism.generation_schema()
    assert {"sceneType", "title", "learningGoal", "entities", "visualProgram", "stages", "conclusion"}.issubset(schema["properties"])
    assert {"sceneType", "title", "learningGoal", "entities", "visualProgram", "stages", "conclusion"}.issubset(schema["required"])
    for operation in ("GeneratedSwapOperation", "GeneratedMoveOperation", "GeneratedMarkCompleteOperation"):
        assert {"type", "entityIds", "reason", "result"}.issubset(schema["$defs"][operation]["required"])


def test_compact_generation_contract_shares_scene_data_and_expands_canonically():
    generated = GeneratedStepThroughMechanism.model_validate({
        "sceneType": "sequence_exchange_scene",
        "title": "Three-message exchange",
        "learningGoal": "Understand how two actors establish shared state.",
        "entities": [
            {"id": "initiator", "kind": "actor", "label": "Initiator"},
            {"id": "responder", "kind": "actor", "label": "Responder"},
        ],
        "visualProgram": {
            "type": "sequence_exchange_scene",
            "actorIds": ["initiator", "responder"],
            "messages": [
                {"id": "request", "sender": "initiator", "receiver": "responder", "label": "Request"},
                {"id": "reply", "sender": "responder", "receiver": "initiator", "label": "Reply"},
            ],
        },
        "stages": [
            {"title": "Request", "explanation": "The initiator opens the exchange.", "visual": {"type": "sequence_exchange_scene", "visibleMessageIds": ["request"], "emphasizedMessageId": "request"}},
            {"title": "Reply", "explanation": "The responder confirms receipt.", "visual": {"type": "sequence_exchange_scene", "visibleMessageIds": ["request", "reply"], "emphasizedMessageId": "reply"}},
        ],
        "conclusion": "The ordered exchange establishes shared state.",
    })

    compact = generated.model_dump(by_alias=True, exclude_none=True, exclude_defaults=True)
    assert "messages" not in compact["stages"][0]["visual"]
    assert "actors" not in compact["stages"][0]["visual"]
    canonical = generated.to_canonical()
    assert isinstance(canonical, StepThroughMechanism)
    assert [message.label for message in canonical.stages[-1].visual.messages] == ["Request", "Reply"]


def test_compact_generation_contract_enforces_complexity_bounds_and_deltas():
    payload = {
        "sceneType": "ordered_items_scene",
        "title": "Ordered change",
        "learningGoal": "Understand why two items change order.",
        "entities": [{"id": "a", "kind": "item", "label": "5"}, {"id": "b", "kind": "item", "label": "3"}],
        "visualProgram": {"type": "ordered_items_scene", "initialOrder": ["a", "b"]},
        "stages": [
            {"title": "Compare", "explanation": "Compare the values.", "visual": {"type": "ordered_items_observe", "operation": {"type": "compare", "entityIds": ["a", "b"], "reason": "5 is greater than 3."}}},
            {"title": "Swap", "explanation": "Put the smaller value first.", "visual": {"type": "ordered_items_reorder", "operation": {"type": "swap", "entityIds": ["a", "b"], "reason": "Ascending order needs 3 first.", "result": "3 now precedes 5."}, "resultingOrder": ["b", "a"]}},
        ],
        "conclusion": "The comparison explains the reorder.",
    }
    generated = GeneratedStepThroughMechanism.model_validate(payload)
    canonical = generated.to_canonical()
    assert [item.entity_id for item in canonical.stages[1].visual.before.items] == ["a", "b"]
    assert [item.entity_id for item in canonical.stages[1].visual.after.items] == ["b", "a"]

    too_many_stages = {**payload, "stages": payload["stages"] * 3}
    with pytest.raises(ValidationError, match="at most 5 items"):
        GeneratedStepThroughMechanism.model_validate(too_many_stages)

    repeated_state = payload.copy()
    repeated_state["stages"] = [dict(payload["stages"][0]), dict(payload["stages"][1])]
    repeated_state["stages"][0]["visual"] = {**repeated_state["stages"][0]["visual"], "before": {"items": []}}
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        GeneratedStepThroughMechanism.model_validate(repeated_state)


def test_compact_vector_generation_expands_without_presentation_geometry():
    generated = GeneratedStepThroughMechanism.model_validate({
        "sceneType": "vector_scene",
        "title": "Remove a shared direction",
        "learningGoal": "Understand how projection identifies directional overlap.",
        "entities": [
            {"id": "input", "kind": "vector", "label": "Input vector"},
            {"id": "basis", "kind": "vector", "label": "Basis direction"},
            {"id": "projection", "kind": "vector", "label": "Projection"},
        ],
        "visualProgram": {"type": "vector_scene"},
        "stages": [
            {"title": "Identify overlap", "explanation": "Project the input onto the basis direction.", "visual": {"type": "vector_scene", "activeEntityIds": ["input", "basis"], "operations": [{"type": "project", "entityIds": ["input", "basis", "projection"], "reason": "The projection isolates the shared direction."}]}},
            {"title": "Separate the component", "explanation": "Highlight the component that can be removed.", "visual": {"type": "vector_scene", "activeEntityIds": ["projection"], "operations": [{"type": "highlight", "entityIds": ["projection"]}], "relationships": [{"source": "projection", "target": "basis", "relation": "parallel_to"}]}},
        ],
        "conclusion": "Projection represents the portion already aligned with the basis direction.",
    })
    canonical = generated.to_canonical()
    assert isinstance(canonical, StepThroughMechanism)
    assert canonical.stages[0].visual.operations[0].type == "project"
    assert "coordinates" not in generated.model_dump_json()


def test_tcp_replay_is_manual_zero_call_sequence_program(client):
    response = client.post("/dev/step-through/generate", json={"fixture_name": "tcp-handshake", "source_text": step_through.SOURCE_FIXTURES["tcp-handshake"], "mode": "replay"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["metadata"]["model_call_count"] == 0
    assert body["metadata"]["fixture_kind"] == "sample_manual"
    assert body["mechanism"]["sceneType"] == "sequence_exchange_scene"
    assert [message["label"] for message in body["mechanism"]["stages"][-1]["visual"]["messages"]] == ["SYN", "SYN-ACK", "ACK"]
