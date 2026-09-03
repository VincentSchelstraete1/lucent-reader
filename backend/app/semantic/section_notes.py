from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.segmentation import LearningBlock
from app.routing import RepresentationDecision
from .schema import LearningObject, PlainTextObject

_SECTION_CACHE: dict[str, SectionNote] = {}
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SectionInput:
    id: str
    title: str | None
    heading_ancestry: list[str]
    learning_block_ids: list[str]
    blocks: list[LearningBlock]
    source: dict[str, Any]


COMPONENT_KINDS = Literal["explanation", "key_definition", "flow", "structure", "relationship_map", "comparison", "worked_example", "equation", "callout", "takeaway"]

class SectionComponent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    kind: COMPONENT_KINDS
    title: str
    text: str = ""
    source_block_ids: list[str] = Field(default_factory=list, alias="sourceBlockIds")
    learning_object: LearningObject | None = Field(default=None, alias="learningObject")
    why_it_matters: str | None = Field(default=None, alias="whyItMatters")
    term: str | None = None
    definition: str | None = None
    significance: str | None = None
    nodes: list[dict] = Field(default_factory=list)
    edges: list[dict] = Field(default_factory=list)
    root: dict | None = None
    items: list[dict] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    conclusion: str | None = None
    problem: str | None = None
    known_values: list[dict] = Field(default_factory=list, alias="knownValues")
    steps: list[dict] = Field(default_factory=list)
    result: str | None = None
    interpretation: str | None = None
    equation: str | None = None
    variables: list[dict] = Field(default_factory=list)
    callout_type: str | None = Field(default=None, alias="calloutType")
    takeaway: str | None = None

    @model_validator(mode="after")
    def validate_semantic_shape(self):
        if not self.source_block_ids:
            raise ValueError("component must cite source blocks")
        if self.kind in {"flow", "relationship_map"}:
            ids = {str(node.get("id")) for node in self.nodes if node.get("id")}
            if not ids or not self.edges or any(not ({str(edge.get("source", edge.get("from"))), str(edge.get("target", edge.get("to")))} <= ids) for edge in self.edges):
                raise ValueError("visual relationship components require connected nodes and edges")
            if any(len(str(edge.get("relation", edge.get("label", "")).split())) > 4 for edge in self.edges):
                if any(len(str(edge.get("relation") or edge.get("label") or "").split()) > 4 for edge in self.edges):
                    raise ValueError("edge labels must be concise")
        if self.kind == "structure" and not self.root:
            raise ValueError("structure components require a root")
        if self.kind == "key_definition" and (not self.term or not self.definition):
            raise ValueError("definitions require a term and definition")
        if self.kind == "worked_example" and not self.steps:
            raise ValueError("worked examples require ordered steps")
        if self.kind == "equation" and not self.equation:
            raise ValueError("equations require an equation")
        if self.kind in {"explanation", "callout", "takeaway"} and not (self.text or self.takeaway):
            raise ValueError("text components require content")
        return self


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
        kind = "explanation" if obj.type == "plain_text" else {"process": "flow", "causal": "flow", "hierarchy": "structure", "quantitative": "worked_example", "comparison": "comparison", "concept_map": "relationship_map"}.get(obj.type, "explanation")
        data = {"kind": kind, "title": obj.title, "text": block.text[:500], "sourceBlockIds": [block.id], "learningObject": obj}
        if kind in {"flow", "relationship_map"}:
            if obj.type == "process":
                data["nodes"] = [{"id": step["id"], "label": step["label"]} for step in obj.steps]
                data["edges"] = [{"source": edge["from"], "target": edge["to"], "relation": "then"} for edge in obj.connections]
            elif obj.type == "causal":
                data["nodes"], data["edges"] = obj.nodes, [{"source": edge.get("from"), "target": edge.get("to"), "relation": edge.get("label", "causes")} for edge in obj.edges]
            else:
                data["nodes"], data["edges"] = obj.nodes, obj.relationships
        elif kind == "structure":
            data["root"] = obj.root
        elif kind == "worked_example":
            data["steps"] = [{"label": step} for step in (obj.derivation_steps or [block.text[:500]])]
        components.append(SectionComponent.model_validate(data))
    return SectionNote(id=section.id, title=section.title or (available[0].title if available else "Learning section"), bigIdea=first_text, learningGoals=["Understand the main idea and how the section's parts connect."], components=components, keyTakeaways=[block.text.strip() for block in section.blocks[:3]], sourceBlockIds=section.learning_block_ids)


def model_section_note(section: SectionInput, *, model_version: str = "section-v1") -> SectionNote:
    """Generate one coherent section note. The cache is process-local V1 and
    deliberately versioned so prompt/schema changes invalidate old results."""
    from app.services.anthropic_service import _run_structured_tool
    source = "\n\n".join(f"[{block.id}] {block.text}" for block in section.blocks)
    key = hashlib.sha256(f"{model_version}:{section.title}:{source}".encode()).hexdigest()
    if key in _SECTION_CACHE:
        logger.info("section_generation_cache_hit section_id=%s title=%r model=claude-haiku-4-5-20251001", section.id, section.title)
        return _SECTION_CACHE[key].model_copy()
    schema = {"type": "object", "properties": {
        "title": {"type": "string"}, "bigIdea": {"type": "string"},
        "learningGoals": {"type": "array", "items": {"type": "string"}},
        "components": {"type": "array", "items": {"type": "object", "properties": {"kind": {"type": "string", "enum": ["explanation", "key_definition", "flow", "structure", "relationship_map", "comparison", "worked_example", "equation", "callout", "takeaway"]}, "title": {"type": "string"}, "text": {"type": "string"}, "sourceBlockIds": {"type": "array", "items": {"type": "string"}}, "whyItMatters": {"type": "string"}, "term": {"type": "string"}, "definition": {"type": "string"}, "significance": {"type": "string"}, "nodes": {"type": "array", "items": {"type": "object"}}, "edges": {"type": "array", "items": {"type": "object"}}, "root": {"type": "object"}, "items": {"type": "array", "items": {"type": "object"}}, "dimensions": {"type": "array", "items": {"type": "string"}}, "conclusion": {"type": "string"}, "problem": {"type": "string"}, "knownValues": {"type": "array", "items": {"type": "object"}}, "steps": {"type": "array", "items": {"type": "object"}}, "result": {"type": "string"}, "interpretation": {"type": "string"}, "equation": {"type": "string"}, "variables": {"type": "array", "items": {"type": "object"}}, "calloutType": {"type": "string"}, "takeaway": {"type": "string"}}, "required": ["kind", "title", "sourceBlockIds"]}},
        "keyTakeaways": {"type": "array", "items": {"type": "string"}}, "omittedNoise": {"type": "array", "items": {"type": "string"}}
    }, "required": ["title", "bigIdea", "learningGoals", "components", "keyTakeaways", "omittedNoise"]}
    started = time.perf_counter()
    logger.info("section_generation_start section_id=%s title=%r model=claude-haiku-4-5-20251001 cache_hit=false", section.id, section.title)
    try:
        raw = _run_structured_tool("Design study notes that teach this coherent section; do not merely summarize it. First identify the learner's mental model, essential relationships, terminology, mechanisms, equations, examples, and removable repetition. Then compose a varied sequence from these components: explanation, key_definition, flow, structure, relationship_map, comparison, worked_example, equation, callout, takeaway. Use a visual component only when its semantic structure is clearer than prose. Keep node labels under about 8 words and edge relations under 4 words. Every component must cite sourceBlockIds from the supplied blocks. Preserve technical detail, stay grounded, and mark no unsupported facts as source-derived.\n\n" + source, "section_learning_note", schema, 1800, timeout=15)
    except Exception as exc:
        logger.exception("section_generation_failure section_id=%s title=%r stage=anthropic_request exception_type=%s latency_ms=%.1f fallback=true", section.id, section.title, type(exc).__name__, (time.perf_counter() - started) * 1000)
        raise
    try:
        note = SectionNote.model_validate({**raw, "id": section.id, "sourceBlockIds": section.learning_block_ids})
    except Exception as exc:
        logger.exception("section_generation_failure section_id=%s title=%r stage=section_note_validation exception_type=%s latency_ms=%.1f fallback=true", section.id, section.title, type(exc).__name__, (time.perf_counter() - started) * 1000)
        raise
    logger.info("section_generation_success section_id=%s title=%r model=claude-haiku-4-5-20251001 latency_ms=%.1f fallback=false components=%d", section.id, section.title, (time.perf_counter() - started) * 1000, len(note.components))
    _SECTION_CACHE[key] = note
    return note.model_copy()


async def generate_sections_concurrently(sections: list[SectionInput], objects: dict[str, LearningObject], *, concurrency: int = 3, use_model: bool = False) -> list[SectionNote]:
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def one(section: SectionInput) -> SectionNote:
        async with semaphore:
            if use_model:
                try:
                    return await asyncio.to_thread(model_section_note, section)
                except Exception as exc:
                    logger.warning("section_generation_fallback section_id=%s title=%r stage=section_task exception_type=%s fallback=true", section.id, section.title, type(exc).__name__)
                    pass
            return deterministic_section_note(section, objects)

    return list(await asyncio.gather(*(one(section) for section in sections)))

async def generate_sections_progressively(sections: list[SectionInput], objects: dict[str, LearningObject], on_complete, *, concurrency: int = 3, use_model: bool = False) -> list[SectionNote]:
    semaphore = asyncio.Semaphore(max(1, concurrency))
    results: list[SectionNote | None] = [None] * len(sections)

    async def one(index: int, section: SectionInput) -> None:
        async with semaphore:
            try:
                note = await asyncio.to_thread(model_section_note, section) if use_model else deterministic_section_note(section, objects)
            except Exception as exc:
                note = deterministic_section_note(section, objects)
                logger.warning("section_generation_fallback section_id=%s title=%r stage=section_task exception_type=%s fallback=true", section.id, section.title, type(exc).__name__)
                await on_complete(index, note, str(exc))
            else:
                await on_complete(index, note, None)
            results[index] = note

    await asyncio.gather(*(one(index, section) for index, section in enumerate(sections)))
    return [note for note in results if note is not None]
