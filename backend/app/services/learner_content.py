"""The explicit boundary between internal tutor state and learner-facing copy.

This module is intentionally small in Phase 1.  It centralizes the existing
content lint so later scene execution can validate every public block in one
place without exposing tutor decisions or evaluation internals.
"""
from __future__ import annotations

import re
from typing import Any

from app.schemas.learn import LearnStep


_BANNED_META_PHRASES = (
    "the teaching point", "source-grounded relationship", "relationship described above",
    "relevant detail", "unrelated detail", "defining relationship", "supporting detail",
    "the concept above", "a related but different idea", "a claim not supported by this material",
    "which response best matches", "the key relationship here", "correct concept",
    "concept described above", "what outcome should occur when", "is applied here",
    "notice how this element connects to the others",
)
_INTERNAL_FIELD_NAMES = {
    "concept_id", "source_id", "source_block", "source_block_id", "interaction_type",
    "target_variable", "scaffold_level", "teaching_point", "repair_step", "mutation_type",
}


def student_text(step: LearnStep) -> str:
    data = step.model_dump(by_alias=True, exclude_none=True)
    values: list[str] = []
    for key in ("title", "prompt", "content", "feedbackCorrect", "feedbackIncorrect", "remediation", "reveal", "solution"):
        if data.get(key):
            values.append(str(data[key]))
    values.extend(str(item) for item in data.get("hints", []))
    for key in ("options", "items", "pairs", "targets", "labels"):
        values.extend(str(item.get("label", "")) for item in data.get(key, []) if isinstance(item, dict))
    visual = data.get("visualSpec") or {}
    values.extend(str(visual.get(key, "")) for key in ("title", "purpose"))
    values.extend(str(node.get("label", "")) + " " + str(node.get("detail", "")) for node in visual.get("nodes", []) if isinstance(node, dict))
    values.extend(str(stage.get("title", "")) + " " + str(stage.get("explanation", "")) for stage in visual.get("stages", []) if isinstance(stage, dict))
    return " ".join(values)


def learner_text_quality_issues(text: str, source_text: str = "") -> list[str]:
    lowered = text.casefold()
    issues = [phrase for phrase in _BANNED_META_PHRASES if phrase in lowered]
    source_lower = source_text.casefold()
    for token in re.findall(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b", text):
        if token.casefold() not in source_lower:
            issues.append(f"internal_identifier:{token}")
    for field_name in _INTERNAL_FIELD_NAMES:
        if field_name in lowered and field_name not in source_lower:
            issues.append(f"internal_field:{field_name}")
    return list(dict.fromkeys(issues))


def student_facing_quality_issues(step: LearnStep, source_text: str = "") -> list[str]:
    return learner_text_quality_issues(student_text(step), source_text)


def extract_source_propositions(source: Any) -> list[str]:
    """Return short source-backed propositions for deterministic fallbacks."""
    if isinstance(source, str):
        text = source
    elif isinstance(source, dict):
        text = " ".join(str(source.get(key, "")) for key in ("bigIdea", "content", "text", "outcome", "result", "interpretation"))
    else:
        text = ""
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if len(sentence.strip()) >= 20][:8]
