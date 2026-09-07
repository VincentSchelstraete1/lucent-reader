"""Deterministic, test-only fixtures for the browser golden journeys.

The real browser remains authenticated through the normal Google/session flow.
This module deliberately does not add an application auth bypass.  It gives
the acceptance suite two substantive, resettable source domains and a stable
way to create a fresh Learn session through the same public API used by the UI.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GoldenDomain:
    key: str
    title: str
    content: str
    section_title: str
    big_idea: str
    takeaway: str
    component_title: str


GOLDEN_DOMAINS = (
    GoldenDomain(
        key="pendulum",
        title="Golden Pendulum Energy",
        content=(
            "In an ideal pendulum, gravitational potential energy becomes kinetic energy "
            "as the bob falls. Total mechanical energy remains conserved; speed is greatest "
            "at the lowest point and zero at each turning point."
        ),
        section_title="Pendulum energy cycle",
        big_idea="Potential energy decreases as kinetic energy increases while total energy stays constant.",
        takeaway="The bottom of the swing has maximum speed and kinetic energy.",
        component_title="Energy conversion example",
    ),
    GoldenDomain(
        key="satire",
        title="Golden Enlightenment Satire",
        content=(
            "Enlightenment satire uses irony and exaggeration to expose a gap between a "
            "speaker's literal statement and the social criticism underneath. The comic "
            "surface is a strategy for making hypocrisy visible, not the whole argument."
        ),
        section_title="Satire as social critique",
        big_idea="Irony creates distance between what is said and the critique the audience infers.",
        takeaway="Exaggeration makes the underlying social contradiction easier to examine.",
        component_title="Irony and exaggeration example",
    ),
)


def seed_golden_domain(client: Any, domain: GoldenDomain) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create one substantive source/document/note and a fresh Learn session."""
    source = client.post("/sources", json={"type": "website", "url": f"https://example.com/golden-{domain.key}"})
    source.raise_for_status()
    document = client.post(
        "/documents",
        json={"source_id": source.json()["id"], "title": domain.title, "content": domain.content},
    )
    document.raise_for_status()
    note = {
        "title": domain.title,
        "sectionNotes": [{
            "id": f"golden-{domain.key}-section",
            "title": domain.section_title,
            "bigIdea": domain.big_idea,
            "sourceBlockIds": [f"golden-{domain.key}-block"],
            "keyTakeaways": [domain.takeaway],
            "components": [{
                "kind": "worked_example",
                "title": domain.component_title,
                "problem": domain.content,
                "result": domain.takeaway,
                "steps": [{"order": 1, "description": domain.big_idea}],
            }],
        }],
    }
    note_response = client.post(
        "/notes",
        json={"title": domain.title, "content_type": "section_note", "document_id": document.json()["id"], "content": json.dumps(note)},
    )
    note_response.raise_for_status()
    session = client.post(
        f"/documents/{document.json()['id']}/learn-sessions",
        json={"goal": "understand", "familiarity": "new", "restart": True},
    )
    session.raise_for_status()
    return document.json(), session.json()

