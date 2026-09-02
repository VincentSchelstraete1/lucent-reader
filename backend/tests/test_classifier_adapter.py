from types import SimpleNamespace

import app.services.anthropic_service as anthropic_service
from app.routing.classifier import AnthropicClassifierAdapter


def _tool_use_response(input_data: dict):
    return SimpleNamespace(content=[SimpleNamespace(type="tool_use", input=input_data)])


def test_classifier_returns_a_valid_type_from_the_tool_response(monkeypatch):
    monkeypatch.setattr(anthropic_service.client.messages, "create", lambda *a, **k: _tool_use_response({"type": "process"}))
    assert AnthropicClassifierAdapter().classify("First, then, finally.") == "process"


def test_classifier_returns_none_on_an_out_of_enum_value(monkeypatch):
    monkeypatch.setattr(anthropic_service.client.messages, "create", lambda *a, **k: _tool_use_response({"type": "not_a_real_type"}))
    assert AnthropicClassifierAdapter().classify("text") is None


def test_classifier_returns_none_when_no_tool_use_block_is_present(monkeypatch):
    monkeypatch.setattr(anthropic_service.client.messages, "create", lambda *a, **k: SimpleNamespace(content=[]))
    assert AnthropicClassifierAdapter().classify("text") is None


def test_classifier_returns_none_on_a_provider_error_rather_than_raising(monkeypatch):
    def _raise(*args, **kwargs):
        raise RuntimeError("network error")

    monkeypatch.setattr(anthropic_service.client.messages, "create", _raise)
    assert AnthropicClassifierAdapter().classify("text") is None


def test_classifier_passes_a_timeout_and_small_max_tokens(monkeypatch):
    captured = {}

    def _create(*args, **kwargs):
        captured.update(kwargs)
        return _tool_use_response({"type": "plain_text"})

    monkeypatch.setattr(anthropic_service.client.messages, "create", _create)
    AnthropicClassifierAdapter(timeout_seconds=3.0, max_tokens=15).classify("text")
    assert captured["timeout"] == 3.0
    assert captured["max_tokens"] == 15
    assert captured["tool_choice"] == {"type": "tool", "name": "classify_representation"}
