from __future__ import annotations

import re
from typing import Any


# Provider responses occasionally describe an extraction/generation failure in
# perfectly valid SectionNote JSON. These phrases are operational diagnostics,
# never learner content. Keep matching centralized so ingestion, indexing, and
# Learn-session boundaries cannot drift apart again.
_SOURCE_DIAGNOSTIC_PATTERNS = tuple(re.compile(pattern, re.IGNORECASE) for pattern in (
    r"\binsufficient source(?: material)?\b",
    r"\bno (?:substantive|usable|source) content(?: (?:was )?provided| available)?\b",
    r"\b(?:unable|failed|could not|cannot) to (?:design|create|generate|build) (?:a |the )?(?:learning experience|lesson|study guide)\b",
    r"\b(?:unable|failed|could not|cannot) to extract\b",
    r"\bextraction (?:error|failed|failure)\b",
    r"\bsource material (?:is )?unavailable\b",
    r"\bdocument contains no (?:extractable )?text\b",
    r"\bsource blocks? contain(?:s)? only metadata\b",
    r"\bmetadata[- ]only source\b",
    r"\bmetadata header\b",
    r"\blearning experience requirements\b",
))


def is_source_diagnostic_text(value: Any) -> bool:
    text = " ".join(str(value or "").split())
    return any(pattern.search(text) for pattern in _SOURCE_DIAGNOSTIC_PATTERNS)


def contains_source_diagnostic(value: Any) -> bool:
    """Recursively detect operational source/generation diagnostics."""
    if hasattr(value, "model_dump"):
        value = value.model_dump(by_alias=True)
    if isinstance(value, dict):
        return any(contains_source_diagnostic(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(contains_source_diagnostic(item) for item in value)
    return is_source_diagnostic_text(value)
