from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.segmentation import LearningBlock
from app.routing import RepresentationDecision
from .schema import LearningObject, PlainTextObject

_SECTION_CACHE: dict[str, SectionNote] = {}


@dataclass(frozen=True)
class SectionInput:
    id: str
    title: str | None
    heading_ancestry: list[str]
    learning_block_ids: list[str]
    blocks: list[LearningBlock]
    source: dict[str, Any]


class SectionComponent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    kind: str
    title: str
    text: str
    source_block_ids: list[str] = Field(default_factory=list, alias="sourceBlockIds")
    learning_object: LearningObject | None = Field(default=None, alias="learningObject")


class SectionNote(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    title: str
    big_idea: str = Field(alias="bigIdea")
    learning_goals: list[str] = Field(default_factory=list, alias="learningGoals")
    components: list[SectionComponent] = Field(default_factory=list)
    key_takeaways: list[str] = Field(default_factory=list, alias="keyTakeaways")
    source_block_ids: list[str] = Field(default_factory=list, alias="sourceBlockIds")
    omitted_noise: list[str] = Field(default_factory=list, alias="omittedNoise")


def group_learning_blocks(blocks: list[LearningBlock], *, max_blocks: int = 6) -> list[SectionInput]:
    """Group adjacent blocks conservatively using existing document structure."""
    sections: list[SectionInput] = []
    current: list[LearningBlock] = []
    current_key: tuple[str, ...] | None = None

    def flush() -> None:
        nonlocal current, current_key
        if not current:
            return
        first = current[0]
        sections.append(SectionInput(
            id=f"section-{len(sections)}",
            title=first.title or (first.heading_ancestry[-1] if first.heading_ancestry else None),
            heading_ancestry=list(first.heading_ancestry),
            learning_block_ids=[block.id for block in current],
            blocks=list(current),
            source={"page_start": min((b.source.page_start for b in current if b.source.page_start is not None), default=None), "page_end": max((b.source.page_end for b in current if b.source.page_end is not None), default=None)},
        ))
        current, current_key = [], None

    for block in blocks:
        key = tuple(block.heading_ancestry)
        if current and (key != current_key or block.title or len(current) >= max_blocks):
            flush()
        current.append(block)
        current_key = key
    flush()
    return sections


def deterministic_section_note(section: SectionInput, objects: dict[str, LearningObject]) -> SectionNote:
    available = [objects[b.id] for b in section.blocks if b.id in objects]
    first_text = section.blocks[0].text.strip() if section.blocks else ""
    components: list[SectionComponent] = []
    for block, obj in zip(section.blocks, [objects.get(b.id) for b in section.blocks]):
        if obj is None:
            continue
        kind = "explanation" if obj.type == "plain_text" else {"process": "flow_or_mechanism", "causal": "flow_or_mechanism", "hierarchy": "hierarchy_or_structure", "quantitative": "worked_example", "comparison": "comparison", "concept_map": "flow_or_mechanism"}.get(obj.type, "explanation")
        components.append(SectionComponent(kind=kind, title=obj.title, text=block.text[:500], sourceBlockIds=[block.id], learningObject=obj))
    return SectionNote(id=section.id, title=section.title or (available[0].title if available else "Learning section"), bigIdea=first_text, learningGoals=["Understand the main idea and how the section's parts connect."], components=components, keyTakeaways=[block.text.strip() for block in section.blocks[:3]], sourceBlockIds=section.learning_block_ids)


def model_section_note(section: SectionInput, *, model_version: str = "section-v1") -> SectionNote:
    """Generate one coherent section note. The cache is process-local V1 and
    deliberately versioned so prompt/schema changes invalidate old results."""
    from app.services.anthropic_service import _run_structured_tool
    source = "\n\n".join(f"[{block.id}] {block.text}" for block in section.blocks)
    key = hashlib.sha256(f"{model_version}:{section.title}:{source}".encode()).hexdigest()
    if key in _SECTION_CACHE:
        return _SECTION_CACHE[key].model_copy()
    schema = {"type": "object", "properties": {
        "title": {"type": "string"}, "bigIdea": {"type": "string"},
        "learningGoals": {"type": "array", "items": {"type": "string"}},
        "components": {"type": "array", "items": {"type": "object", "properties": {"kind": {"type": "string"}, "title": {"type": "string"}, "text": {"type": "string"}, "sourceBlockIds": {"type": "array", "items": {"type": "string"}}}, "required": ["kind", "title", "text", "sourceBlockIds"]}},
        "keyTakeaways": {"type": "array", "items": {"type": "string"}}, "omittedNoise": {"type": "array", "items": {"type": "string"}}
    }, "required": ["title", "bigIdea", "learningGoals", "components", "keyTakeaways", "omittedNoise"]}
    raw = _run_structured_tool("Teach this coherent section as one set of grounded notes. Collapse repetition, preserve essential mechanisms, and choose prose or a flow/structure/example component only when it improves understanding. Use only the supplied blocks; every component must cite one or more sourceBlockIds. Do not invent unsupported facts.\n\n" + source, "section_learning_note", schema, 1400, timeout=15)
    note = SectionNote.model_validate({**raw, "id": section.id, "sourceBlockIds": section.learning_block_ids})
    _SECTION_CACHE[key] = note
    return note.model_copy()


async def generate_sections_concurrently(sections: list[SectionInput], objects: dict[str, LearningObject], *, concurrency: int = 3, use_model: bool = False) -> list[SectionNote]:
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def one(section: SectionInput) -> SectionNote:
        async with semaphore:
            if use_model:
                try:
                    return await asyncio.to_thread(model_section_note, section)
                except Exception:
                    pass
            return deterministic_section_note(section, objects)

    return list(await asyncio.gather(*(one(section) for section in sections)))
