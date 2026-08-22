from types import SimpleNamespace

import pytest

import app.services.anthropic_service as anthropic_service


def _tool_use_response(input_data: dict):
    return SimpleNamespace(content=[SimpleNamespace(type="tool_use", input=input_data)])


@pytest.fixture()
def mock_generated_note(monkeypatch):
    def _create(*args, **kwargs):
        return _tool_use_response({
            "title": "Mock Note",
            "summary": "A mock summary.",
            "key_points": ["Point one", "Point two"],
            "concepts": ["Concept A"],
            "sections": [{"heading": "Intro", "content": "Some content."}]
        })

    monkeypatch.setattr(anthropic_service.client.messages, "create", _create)


@pytest.fixture()
def mock_quiz(monkeypatch):
    def _create(*args, **kwargs):
        questions = [
            {
                "question": f"Question {i}?",
                "choices": ["A", "B", "C", "D"],
                "correct_index": 0,
                "explanation": "Because A is correct."
            }
            for i in range(3)
        ]
        return _tool_use_response({"questions": questions})

    monkeypatch.setattr(anthropic_service.client.messages, "create", _create)


@pytest.fixture()
def mock_invalid_structured_output(monkeypatch):
    def _create(*args, **kwargs):
        # Missing every required field but title - proves the endpoint
        # rejects a malformed model response instead of saving it.
        return _tool_use_response({"title": "Missing fields"})

    monkeypatch.setattr(anthropic_service.client.messages, "create", _create)
