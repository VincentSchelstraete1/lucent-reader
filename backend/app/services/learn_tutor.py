"""Optional, bounded semantic tutor helpers.

The runtime remains deterministic by default.  When explicitly enabled, this
module lets the model diagnose a response and choose a validated remediation
category; it cannot mutate session state or emit executable UI code.
"""
from __future__ import annotations

import os

from app.schemas.learn import LearnEvaluation

DIAGNOSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "result": {"type": "string", "enum": ["correct", "partially_correct", "incorrect", "insufficient_evidence"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "misconception": {"type": ["string", "null"]},
        "evidence": {"type": "string"},
        "remediationCategory": {"type": "string", "enum": ["none", "simplify", "example", "prerequisite", "change_modality", "revisit"]},
    },
    "required": ["result", "confidence", "misconception", "evidence", "remediationCategory"],
}


def diagnose_response(*, prompt: str, expected: str, response: str, source_context: str, fallback: LearnEvaluation) -> LearnEvaluation:
    """Diagnose a free response when the opt-in model flag is enabled.

    A failure, missing key, or malformed tool result always returns the
    deterministic fallback, preserving session reliability and cost bounds.
    """
    if os.getenv("LEARN_TUTOR_MODEL_ENABLED", "0").lower() not in {"1", "true", "yes"}:
        return fallback
    try:
        from app.services.anthropic_service import _run_structured_tool
        raw = _run_structured_tool(
            "Evaluate the learner response against the source-grounded teaching point. "
            "Identify a specific misconception only when supported; otherwise use null. "
            "Choose one remediation category that would teach the idea differently. "
            f"\nSource context:\n{source_context[:5000]}\nPrompt: {prompt}\nExpected idea: {expected}\nLearner response: {response[:1200]}",
            "learn_response_evaluation", DIAGNOSIS_SCHEMA, max_tokens=420, max_retries=0,
        )
        return LearnEvaluation.model_validate(raw)
    except Exception:
        return fallback
