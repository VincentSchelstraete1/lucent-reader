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
