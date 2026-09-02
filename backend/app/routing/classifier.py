"""Cheap classifier fallback for uncertain deterministic routing decisions.

Reuses the existing backend Anthropic structured-output infrastructure
(app.services.anthropic_service._run_structured_tool - the same
tool_choice-enforced strict-schema pattern already used for
generate_structured_note/generate_quiz_questions) rather than building a
second, parallel LLM-calling path. The provider is isolated behind
ClassifierAdapter so routing code never imports Anthropic directly, and a
secret never needs to reach client-side code - this only ever runs
server-side, the same as every other AI call in this app.
"""

from typing import Protocol

from app.routing.representation_types import REPRESENTATION_TYPES, RepresentationType


CLASSIFICATION_TOOL_NAME = "classify_representation"
CLASSIFICATION_SCHEMA = {
    "type": "object",
    "properties": {"type": {"type": "string", "enum": REPRESENTATION_TYPES}},
    "required": ["type"],
}
CLASSIFICATION_PROMPT_TEMPLATE = (
    "Classify which single representation best fits this educational text. "
    "Answer only by calling the tool - no explanation.\n\n"
    "process: an ordered sequence of steps\n"
    "comparison: contrasts two or more things\n"
    "causal: a cause-and-effect relationship\n"
    "concept_map: a network of related concepts\n"
    "hierarchy: a part-to-whole or category structure\n"
    "quantitative: a numeric or mathematical relationship\n"
    "plain_text: none of the above - a plain definition or description\n\n"
    "Text:\n{text}"
)
# 20 was tried first and is too small: Claude's tool_use response includes
# enough surrounding structure (block id, name, opening JSON) that a 20-token
# budget hit stop_reason="max_tokens" before the {"type": "..."} argument
# finished streaming, leaving an empty, useless input dict. Verified against
# the real API - see Checkpoint F's evaluation notes.
DEFAULT_TIMEOUT_SECONDS = 8.0
DEFAULT_MAX_TOKENS = 60


class ClassifierAdapter(Protocol):
    def classify(self, text: str) -> RepresentationType | None:
        """Return a representation type, or None if classification failed
        (timeout, error, malformed response) - callers must treat None as
        "keep the deterministic decision", never as a type on its own."""
        ...


class AnthropicClassifierAdapter:
    def __init__(self, *, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS, max_tokens: int = DEFAULT_MAX_TOKENS) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_tokens = max_tokens

    def classify(self, text: str) -> RepresentationType | None:
        from app.services.anthropic_service import _run_structured_tool

        try:
            result = _run_structured_tool(
                CLASSIFICATION_PROMPT_TEMPLATE.format(text=text),
                CLASSIFICATION_TOOL_NAME,
                CLASSIFICATION_SCHEMA,
                max_tokens=self._max_tokens,
                timeout=self._timeout_seconds,
            )
        except Exception:
            return None

        value = result.get("type") if isinstance(result, dict) else None
        return value if value in REPRESENTATION_TYPES else None
