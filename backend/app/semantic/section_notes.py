from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from app.segmentation import LearningBlock
from app.routing import RepresentationDecision
from .schema import LearningObject, PlainTextObject

_SECTION_CACHE: dict[str, SectionNote] = {}
logger = logging.getLogger(__name__)
SECTION_NOTE_MAX_TOKENS = 1600
SECTION_NOTE_TIMEOUT_SECONDS = 20


@dataclass(frozen=True)
class SectionInput:
    id: str
    title: str | None
    heading_ancestry: list[str]
    learning_block_ids: list[str]
    blocks: list[LearningBlock]
    source: dict[str, Any]


def is_low_value_section(section: SectionInput) -> bool:
    """Conservatively exclude extraction furniture from expensive generation."""
    title = (section.title or "").strip()
    text = "\n".join(block.text for block in section.blocks).strip()
    if not text or len(text) < 8:
        return True
    if title and (len(title) <= 1 or title.lower().rstrip(":") in {"references", "bibliography", "contents", "table of contents"}):
        return True
    if title and any(marker in title.lower() for marker in ("references", "bibliography")):
        return True
    return False


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


class GraphNode(BaseModel):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1, max_length=120)
    explanation: str | None = None


class GraphEdge(BaseModel):
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    relation: str = Field(min_length=1, max_length=80)
    explanation: str | None = None

    @model_validator(mode="after")
    def concise_relation(self):
        if len(self.relation.split()) > 4 or self.relation.lower() == "related to":
            raise ValueError("relationship labels must be concise and meaningful")
        return self


class _TypedComponent(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    title: str = Field(min_length=1)
    source_block_ids: list[str] = Field(alias="sourceBlockIds", min_length=1)
    # Compatibility/debug metadata populated by deterministic conversion; it
    # is excluded from the model-generation JSON schema.
    learning_object: LearningObject | None = Field(default=None, alias="learningObject", exclude=True)


class ExplanationComponent(_TypedComponent):
    kind: Literal["explanation"]
    text: str = Field(min_length=1)
    why_it_matters: str | None = Field(default=None, alias="whyItMatters")


class KeyDefinitionComponent(_TypedComponent):
    kind: Literal["key_definition"]
    term: str = Field(min_length=1)
    definition: str = Field(min_length=1)
    significance: str | None = None


class FlowComponent(_TypedComponent):
    kind: Literal["flow"]
    nodes: list[GraphNode] = Field(min_length=2)
    edges: list[GraphEdge] = Field(min_length=1)
    transition_explanation: str | None = Field(default=None, alias="transitionExplanation")

    @model_validator(mode="after")
    def connected_sequence(self):
        ids = {node.id for node in self.nodes}
        if any(edge.source not in ids or edge.target not in ids for edge in self.edges):
            raise ValueError("flow edges must reference existing nodes")
        if len({edge.source for edge in self.edges} | {edge.target for edge in self.edges}) < 2:
            raise ValueError("flow must contain a real sequence")
        return self


class TreeNode(BaseModel):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1, max_length=120)
    explanation: str | None = None
    children: list["TreeNode"] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_descendants(self):
        ids = [self.id] + [child.id for child in self.children]
        if len(ids) != len(set(ids)):
            raise ValueError("structure tree contains duplicate node IDs")
        return self


class StructureComponent(_TypedComponent):
    kind: Literal["structure"]
    root: TreeNode


class RelationshipMapComponent(_TypedComponent):
    kind: Literal["relationship_map"]
    nodes: list[GraphNode] = Field(min_length=2)
    edges: list[GraphEdge] = Field(min_length=1)

    @model_validator(mode="after")
    def connected_graph(self):
        ids = {node.id for node in self.nodes}
        if any(edge.source not in ids or edge.target not in ids for edge in self.edges):
            raise ValueError("relationship edges must reference existing nodes")
        seen = {next(iter(ids))}
        changed = True
        while changed:
            changed = False
            for edge in self.edges:
                if edge.source in seen or edge.target in seen:
                    before = len(seen)
                    seen.update((edge.source, edge.target))
                    changed = changed or len(seen) != before
        if seen != ids:
            raise ValueError("relationship map must be connected")
        return self


class ComparisonItem(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    values: dict[str, str] = Field(min_length=1)


class ComparisonComponent(_TypedComponent):
    kind: Literal["comparison"]
    items: list[ComparisonItem] = Field(min_length=2)
    dimensions: list[str] = Field(min_length=1)
    why_it_matters: str | None = Field(default=None, alias="whyItMatters")

    @model_validator(mode="after")
    def aligned_dimensions(self):
        expected = set(self.dimensions)
        if any(set(item.values) != expected for item in self.items):
            raise ValueError("comparison values must align across dimensions")
        return self


class WorkedExampleStep(BaseModel):
    order: int = Field(ge=1)
    description: str = Field(min_length=1)


class WorkedExampleComponent(_TypedComponent):
    kind: Literal["worked_example"]
    problem: str = Field(min_length=1)
    known_values: list[dict[str, str]] = Field(default_factory=list, alias="knownValues")
    steps: list[WorkedExampleStep] = Field(min_length=1)
    result: str = Field(min_length=1)
    interpretation: str = Field(min_length=1)

    @model_validator(mode="after")
    def ordered_steps(self):
        if [step.order for step in self.steps] != sorted(step.order for step in self.steps):
            raise ValueError("worked example steps must be ordered")
        return self


class EquationComponent(_TypedComponent):
    kind: Literal["equation"]
    equation: str = Field(min_length=1)
    variables: list[dict[str, str]] = Field(default_factory=list)
    known_values: list[dict[str, str]] = Field(default_factory=list, alias="knownValues")
    substitution: str | None = None
    result: str | None = None
    interpretation: str | None = None


class CalloutComponent(_TypedComponent):
    kind: Literal["callout"]
    text: str = Field(min_length=1)
    callout_type: str | None = Field(default=None, alias="calloutType")
    why_it_matters: str | None = Field(default=None, alias="whyItMatters")


class TakeawayComponent(_TypedComponent):
    kind: Literal["takeaway"]
    takeaway: str = Field(min_length=1)


TypedSectionComponent = Annotated[Union[
    ExplanationComponent, KeyDefinitionComponent, FlowComponent,
    StructureComponent, RelationshipMapComponent, ComparisonComponent,
    WorkedExampleComponent, EquationComponent, CalloutComponent,
    TakeawayComponent,
], Field(discriminator="kind")]
TreeNode.model_rebuild()


class SectionNote(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    title: str
    big_idea: str = Field(alias="bigIdea")
    learning_goals: list[str] = Field(default_factory=list, alias="learningGoals")
    components: list[TypedSectionComponent] = Field(default_factory=list)
    key_takeaways: list[str] = Field(default_factory=list, alias="keyTakeaways")
    source_block_ids: list[str] = Field(default_factory=list, alias="sourceBlockIds")
    omitted_noise: list[str] = Field(default_factory=list, alias="omittedNoise")


class GeneratedSectionNote(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    title: str
    big_idea: str = Field(alias="bigIdea")
    learning_goals: list[str] = Field(alias="learningGoals")
    components: list[TypedSectionComponent]
    key_takeaways: list[str] = Field(alias="keyTakeaways")
    omitted_noise: list[str] = Field(alias="omittedNoise")


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
    def usable(value: str | None) -> bool:
        normalized = (value or "").strip().lower()
        return bool(normalized) and normalized not in {"<unknown>", "$", "n/a", "none"}

    available = [objects[b.id] for b in section.blocks if b.id in objects and usable(b.text)]
    first_text = next((b.text.strip() for b in section.blocks if usable(b.text)), "")
    components: list[SectionComponent] = []
    for block, obj in zip(section.blocks, [objects.get(b.id) for b in section.blocks]):
        if obj is None or not usable(block.text):
            continue
        kind = "explanation" if obj.type == "plain_text" else {"process": "flow", "causal": "flow", "hierarchy": "structure", "quantitative": "worked_example", "comparison": "comparison", "concept_map": "relationship_map"}.get(obj.type, "explanation")
        title = obj.title if usable(obj.title) else (section.title if usable(section.title) else "Explanation")
        data = {"kind": kind, "title": title, "text": block.text[:500], "sourceBlockIds": [block.id], "learningObject": obj}
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
        # Deterministic output is a safety net, so it must never emit a
        # visually-typed component that cannot satisfy the same invariants as
        # model output.  If the LearningObject lacks a connected graph/tree,
        # retain the source-grounded text as an explanation instead.
        try:
            components.append(TypeAdapter(TypedSectionComponent).validate_python(data))
        except ValueError:
            components.append(ExplanationComponent(
                kind="explanation",
                title=title,
                text=block.text[:500],
                sourceBlockIds=[block.id],
                learningObject=obj,
            ))
    title = section.title if usable(section.title) else (available[0].title if available else "Learning section")
    takeaways = [block.text.strip() for block in section.blocks if usable(block.text)][:3]
    return SectionNote(id=section.id, title=title, bigIdea=first_text or title, learningGoals=["Understand the main idea and how the section's parts connect."], components=components, keyTakeaways=takeaways or [title], sourceBlockIds=section.learning_block_ids)


def safe_deterministic_section_note(section: SectionInput, objects: dict[str, LearningObject]) -> SectionNote:
    """Return a valid, source-grounded note even when a specialized fallback fails."""
    try:
        return deterministic_section_note(section, objects)
    except Exception:
        block = next(iter(section.blocks), None)
        source_id = block.id if block else (section.learning_block_ids[0] if section.learning_block_ids else section.id)
        text = (block.text.strip() if block else "") or section.title or "This section could not be generated."
        title = section.title or "Learning section"
        component = ExplanationComponent(kind="explanation", title=title, text=text[:1000], sourceBlockIds=[source_id])
        return SectionNote(id=section.id, title=title, bigIdea=text[:500], learningGoals=["Review the source-grounded explanation."], components=[component], keyTakeaways=[text[:300]], sourceBlockIds=section.learning_block_ids or [source_id])


def model_section_note(section: SectionInput, *, model_version: str = "section-v2-golden") -> SectionNote:
    """Generate one coherent section note. The cache is process-local V1 and
    deliberately versioned so prompt/schema changes invalidate old results."""
    from app.services.anthropic_service import _run_structured_tool
    source = "\n\n".join(f"[{block.id}] {block.text}" for block in section.blocks)
    key = hashlib.sha256(f"{model_version}:{section.title}:{source}".encode()).hexdigest()
    if key in _SECTION_CACHE:
        logger.info("section_generation_cache_hit section_id=%s title=%r model=claude-haiku-4-5-20251001", section.id, section.title)
        return _SECTION_CACHE[key].model_copy()
    schema = GeneratedSectionNote.model_json_schema(by_alias=True)
    started = time.perf_counter()
    logger.info("section_generation_start section_id=%s title=%r model=claude-haiku-4-5-20251001 cache_hit=false source_chars=%d blocks=%d max_tokens=%d", section.id, section.title, len(source), len(section.blocks), SECTION_NOTE_MAX_TOKENS)
    try:
        prompt = ("Design a source-grounded learning experience for this coherent section; do not merely summarize or split the source into prose cards. "
                  "First identify the central mental model and the conceptual bottleneck a learner must overcome. Then compose a short, coherent sequence "
                  "of only the components that materially improve understanding (usually 2–5 strong components; never emit every type by default). "
                  "Use an explanation only for ideas that are genuinely clearer as prose. For a process, mechanism, or causal chain prefer a FLOW with 2+ concise nodes, "
                  "meaningful short verb relations, and a separate brief explanation of why transitions matter. For containment or levels prefer a connected STRUCTURE "
                  "with an explicit root and children. For equations or numerical reasoning prefer EQUATION or WORKED_EXAMPLE with variables, supplied values, ordered "
                  "substitution/derivation steps, result, and interpretation. For systems of concepts use a selective connected RELATIONSHIP_MAP (3–7 concepts) with "
                  "specific relations such as uses, maps, caches, contains, enables, or depends on; never use generic related to. Preserve technical terminology, mechanisms, "
                  "equations, units, and caveats supported by the source. Remove repetition and extraction noise. Keep labels concise and explanations to a few sentences. "
                  "Every component must cite sourceBlockIds from the supplied blocks, and all required fields must be present.\n\n" + source)
        raw = _run_structured_tool(prompt, "section_learning_note", schema, SECTION_NOTE_MAX_TOKENS, timeout=SECTION_NOTE_TIMEOUT_SECONDS, max_retries=0)
    except Exception as exc:
        logger.exception("section_generation_failure section_id=%s title=%r stage=anthropic_request exception_type=%s latency_ms=%.1f fallback=true", section.id, section.title, type(exc).__name__, (time.perf_counter() - started) * 1000)
        raise
    try:
        logger.info("section_generation_response section_id=%s title=%r top_level_keys=%s", section.id, section.title, sorted(raw.keys()) if isinstance(raw, dict) else [])
        generated = GeneratedSectionNote.model_validate(raw)
        note = SectionNote.model_validate({**generated.model_dump(by_alias=True), "id": section.id, "sourceBlockIds": section.learning_block_ids})
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
            return safe_deterministic_section_note(section, objects)

    return list(await asyncio.gather(*(one(section) for section in sections if not is_low_value_section(section))))

async def generate_sections_progressively(sections: list[SectionInput], objects: dict[str, LearningObject], on_complete, *, concurrency: int = 3, use_model: bool = False) -> list[SectionNote]:
    semaphore = asyncio.Semaphore(max(1, concurrency))
    active = [(index, section) for index, section in enumerate(sections) if not is_low_value_section(section)]
    results: list[SectionNote | None] = [None] * len(sections)

    async def one(index: int, section: SectionInput) -> None:
        async with semaphore:
            try:
                note = await asyncio.to_thread(model_section_note, section) if use_model else deterministic_section_note(section, objects)
            except Exception as exc:
                note = safe_deterministic_section_note(section, objects)
                logger.warning("section_generation_fallback section_id=%s title=%r stage=section_task exception_type=%s fallback=true", section.id, section.title, type(exc).__name__)
                await on_complete(index, note, str(exc))
            else:
                await on_complete(index, note, None)
            results[index] = note

    await asyncio.gather(*(one(index, section) for index, section in active))
    return [note for note in results if note is not None]
