"""Deterministic pedagogical policy helpers shared by the Learn runtime/tests."""
from __future__ import annotations

from dataclasses import dataclass

CONTENT_POLICIES = {
    "CONCEPTUAL": {"strategies": ["CONCEPTUAL_EXPLANATION", "EXAMPLE_NONEXAMPLE", "SOCRATIC_PROBE", "TRANSFER_PRACTICE"], "evidence": ["explanation", "transfer"], "escalation": ["ANALOGY", "CONTRAST_CASE", "PREREQUISITE_REPAIR"]},
    "PROCESS": {"strategies": ["ANIMATED_MECHANISM", "GUIDED_DISCOVERY", "RETRIEVAL_PRACTICE", "TRANSFER_PRACTICE"], "evidence": ["recognition", "application", "transfer"], "escalation": ["VISUAL_MODEL", "ERROR_CORRECTION", "PREREQUISITE_REPAIR"]},
    "QUANTITATIVE": {"strategies": ["WORKED_EXAMPLE", "SCAFFOLDED_PRACTICE", "TRANSFER_PRACTICE"], "evidence": ["application", "transfer"], "escalation": ["DECREASE_DIFFICULTY", "PREREQUISITE_REPAIR"]},
    "MEMORIZATION": {"strategies": ["DIRECT_INSTRUCTION", "RETRIEVAL_PRACTICE", "DELAYED_RECHECK"], "evidence": ["recall", "recognition"], "escalation": ["SIMPLIFY", "DELAYED_RECHECK"]},
    "CS_SYSTEMS": {"strategies": ["VISUAL_MODEL", "GUIDED_DISCOVERY", "TRANSFER_PRACTICE"], "evidence": ["recognition", "explanation", "application"], "escalation": ["ERROR_CORRECTION", "PREREQUISITE_REPAIR"]},
}

SCAFFOLD_LEVELS = ("FULL", "GUIDED", "PARTIAL", "INDEPENDENT", "TRANSFER")


def content_policy(objective: dict) -> str:
    explicit = objective.get("contentPolicy") or objective.get("content_policy")
    if explicit in CONTENT_POLICIES:
        return explicit
    text = f"{objective.get('title', '')} {objective.get('outcome', '')}".lower()
    if any(word in text for word in ("algorithm", "cache", "packet", "memory", "system", "protocol")):
        return "CS_SYSTEMS"
    if any(word in text for word in ("calculate", "equation", "derivative", "force", "velocity", "energy", "solve")):
        return "QUANTITATIVE"
    if any(word in text for word in ("sequence", "process", "cycle", "pathway", "mechanism", "reaction")):
        return "PROCESS"
    if any(word in text for word in ("define", "term", "vocabulary", "remember", "identify")):
        return "MEMORIZATION"
    return "CONCEPTUAL"


def next_scaffold(current: str | None, result: str, hints: int = 0, independent: bool = False) -> str:
    level = current if current in SCAFFOLD_LEVELS else "FULL"
    idx = SCAFFOLD_LEVELS.index(level)
    if result in {"incorrect", "partially_correct"}:
        return SCAFFOLD_LEVELS[max(0, idx - 1)]
    if result == "correct":
        if independent:
            return SCAFFOLD_LEVELS[min(len(SCAFFOLD_LEVELS) - 1, idx + 1)]
        return level
    return level


def review_due(result: str, *, hints: int = 0, scaffold: str = "FULL", transfer: bool = False, delayed: bool = False) -> str | None:
    if result in {"incorrect", "partially_correct"}:
        return "LATER_THIS_SESSION"
    if delayed or transfer:
        return "FUTURE_REVIEW"
    if hints or scaffold not in {"INDEPENDENT", "TRANSFER"}:
        return "NEXT_SESSION"
    return "NEXT_SESSION"


def prerequisite_ids(objective: dict, concepts: list[dict]) -> list[str]:
    declared = objective.get("prerequisiteIds") or objective.get("prerequisite_ids") or []
    if declared:
        return [str(item) for item in declared]
    required: set[str] = set()
    for step in objective.get("steps", []):
        required.update(str(item) for item in step.get("requiredConcepts", []) if item)
    known = {str(item.get("conceptId")): item for item in concepts}
    return [cid for cid in required if cid in known and known[cid].get("state") in {"NOT_SEEN", "STRUGGLING", "NEEDS_REVIEW"}]


def diagnose_fallback(result: str, step_type: str, response: str | None = None) -> tuple[str, str | None]:
    if result == "insufficient_evidence":
        return "INSUFFICIENT_EVIDENCE", None
    if result == "partially_correct":
        return "UNCERTAINTY", None
    if result == "correct":
        return "NONE", None
    if step_type in {"problem", "worked_step", "numeric", "ordering"}:
        return "PROCEDURAL_ERROR", None
    return "KNOWLEDGE_GAP", None

