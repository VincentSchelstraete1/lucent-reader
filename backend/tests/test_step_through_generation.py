from app.routers import step_through


def test_live_generation_makes_one_call_and_rejects_invalid_output(client, monkeypatch):
    calls = 0

    def fake_call(*args, **kwargs):
        nonlocal calls
        calls += 1
        return {"title": "incomplete"}

    monkeypatch.setattr(step_through, "_run_structured_tool", fake_call)
    response = client.post("/dev/step-through/generate", json={
        "fixture_name": "bubble-sort",
        "source_text": "Compare adjacent elements and swap them when out of order.",
        "mode": "live",
    })
    assert response.status_code == 422
    assert calls == 1
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_generation"
    assert detail["validation_errors"]
    assert any(error["location"] == "sceneType" for error in detail["validation_errors"])


def test_live_generation_accepts_one_valid_visual_program_with_one_call(client, monkeypatch):
    calls = 0

    def fake_call(*args, **kwargs):
        nonlocal calls
        calls += 1
        assert kwargs["max_retries"] == 0
        return step_through._ordered_replay("bubble-sort").model_dump(by_alias=True)

    monkeypatch.setattr(step_through, "_run_structured_tool", fake_call)
    response = client.post("/dev/step-through/generate", json={
        "fixture_name": "unseen-ordered-process",
        "source_text": "Items are compared, exchanged when needed, and progressively marked complete.",
        "mode": "live",
    })
    assert response.status_code == 200, response.text
    assert calls == 1
    assert response.json()["metadata"]["model_call_count"] == 1
    assert response.json()["mechanism"]["sceneType"] == "ordered_items_scene"
