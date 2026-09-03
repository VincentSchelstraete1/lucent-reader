from app.schemas.step_through import StepThroughMechanism


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
        }, {"title": "Done", "explanation": "The exchange completes."}],
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
