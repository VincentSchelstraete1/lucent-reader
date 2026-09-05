"""Small deterministic retrieval layer for grounded Learn context.

This is intentionally dependency-free for V1: persisted SectionNotes are already
chunked by section and carry stable source block IDs. Token overlap selects the
most relevant bounded context; an embedding index can replace this seam later.
"""
from __future__ import annotations

import re

def retrieve_note_context(note_payload: dict, query: str, limit: int = 3) -> dict:
    terms = {t for t in re.findall(r"[a-z0-9]{3,}", query.lower())}
    scored = []
    for section in note_payload.get("sectionNotes", []):
        text = " ".join([str(section.get("title", "")), str(section.get("bigIdea", "")), *[str(x) for x in section.get("keyTakeaways", [])]])
        score = len(terms & set(re.findall(r"[a-z0-9]{3,}", text.lower())))
        scored.append((score, section))
    # Zero-overlap sections are not evidence for the question.  Keep the
    # bounded fallback only when no section matches at all, so unrelated
    # material is never presented as grounded context.
    ranked = sorted(scored, key=lambda item: item[0], reverse=True)
    matched = [item for item in ranked if item[0] > 0]
    selected = (matched or ranked[:1])[:limit]
    return {"text": "\n\n".join(str(item[1].get("bigIdea", "")) for item in selected if item[1].get("bigIdea")), "sourceSectionIds": [str(item[1].get("id")) for item in selected if item[1].get("id")], "sourceBlockIds": [str(block) for item in selected for block in item[1].get("sourceBlockIds", [])]}
