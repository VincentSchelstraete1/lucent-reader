from types import SimpleNamespace

import httpx
from anthropic import APITimeoutError

from app.routers import step_through
from app.services import anthropic_service
from app.services.anthropic_service import StructuredToolTruncatedError


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
        assert kwargs["timeout"] == 25
        assert args[3] == 1800
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


def test_live_timeout_is_reported_as_timeout_without_retry(client, monkeypatch):
    calls = 0

    def fake_call(*args, **kwargs):
        nonlocal calls
        calls += 1
        assert kwargs["max_retries"] == 0
        raise APITimeoutError(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))

    monkeypatch.setattr(step_through, "_run_structured_tool", fake_call)
    response = client.post("/dev/step-through/generate", json={
        "fixture_name": "bubble-sort",
        "source_text": step_through.SOURCE_FIXTURES["bubble-sort"],
        "mode": "live",
    })
    assert response.status_code == 504
    assert calls == 1
    assert response.json()["detail"]["code"] == "generation_timeout"
    assert "No retry was attempted" in response.json()["detail"]["message"]


def test_live_truncation_is_not_mislabeled_as_validation_failure(client, monkeypatch):
    calls = 0

    def fake_call(*args, **kwargs):
        nonlocal calls
        calls += 1
        assert kwargs["max_retries"] == 0
        raise StructuredToolTruncatedError(input_tokens=950, output_tokens=1800, max_tokens=1800)

    monkeypatch.setattr(step_through, "_run_structured_tool", fake_call)
    response = client.post("/dev/step-through/generate", json={
        "fixture_name": "bubble-sort",
        "source_text": step_through.SOURCE_FIXTURES["bubble-sort"],
        "mode": "live",
    })
    assert response.status_code == 422
    assert calls == 1
    detail = response.json()["detail"]
    assert detail["code"] == "generation_truncated"
    assert "1800-token output budget" in detail["message"]
    assert "No retry was attempted" in detail["message"]


def test_structured_tool_detects_provider_max_token_stop(monkeypatch):
    response = SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", input={"title": "partial"})],
        model="claude-haiku-4-5-20251001",
        stop_reason="max_tokens",
        usage=SimpleNamespace(input_tokens=900, output_tokens=1800),
    )
    request_client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))
    monkeypatch.setattr(anthropic_service.client, "with_options", lambda **kwargs: request_client)

    try:
        anthropic_service._run_structured_tool(
            "prompt",
            "step_through_mechanism",
            {"type": "object"},
            1800,
            timeout=25,
            max_retries=0,
        )
    except StructuredToolTruncatedError as exc:
        assert exc.input_tokens == 900
        assert exc.output_tokens == 1800
        assert exc.max_tokens == 1800
    else:
        raise AssertionError("Expected max_tokens stop reason to be classified as truncation")
