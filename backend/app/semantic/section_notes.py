from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from app.segmentation import LearningBlock
from app.routing import RepresentationDecision
from app.schemas.step_through import GeneratedStepThroughMechanism, StepThroughMechanism
from .schema import LearningObject, PlainTextObject

_SECTION_CACHE: dict[str, SectionNote] = {}
logger = logging.getLogger(__name__)
SECTION_NOTE_MAX_TOKENS = 1600
SECTION_NOTE_TIMEOUT_SECONDS = 20


def _normalize_generated_section_payload(raw: Any) -> Any:
    """Normalize transport-level JSON strings before strict validation.

    Some provider/tool responses have encoded an otherwise valid array as a
    JSON string. Decode only the known structured collection fields; the
    resulting value still passes the complete GeneratedSectionNote and
    canonical SectionNote validators below. No fields are invented or
    discarded.
    """
    if not isinstance(raw, dict):
        return raw
    normalized = dict(raw)
    for field_name in ("components", "learningGoals", "keyTakeaways", "omittedNoise"):
        value = normalized.get(field_name)
        if isinstance(value, str):
            try:
                decoded = json.loads(value)
            except json.JSONDecodeError:
                continue
            if isinstance(decoded, list):
                normalized[field_name] = decoded
    return normalized


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
    normalized_title = title.lower().rstrip(":")
    if title and (len(title) <= 1 or normalized_title in {"references", "bibliography", "contents", "table of contents", "agenda", "today's topics"}):
        return True
    if title and any(marker in normalized_title for marker in ("references", "bibliography", "course administration", "course logistics", "grading and deadlines")):
        return True
    normalized_text = " ".join(text.lower().split())
    # Credits and attribution lines are extraction metadata, not learning
    # content. Suppress only short standalone attributions so captions that
    # explain a figure remain eligible for generation.
    if len(normalized_text) < 240 and re.match(r"^(?:figure|fig\.?|image)\s+(?:by|courtesy of|source:)", normalized_text):
        return True
    if normalized_title in {"<unknown>", "unknown"} and len(normalized_text) < 80:
        return True
    if normalized_text in {normalized_title, "<unknown>", "unknown"}:
        return True
    # Suppress short title/agenda furniture without suppressing concise real
    # definitions. These signals describe administrative metadata rather than
    # a specific course or document.
    administrative_terms = ("due date", "regrade", "office hours", "extension request", "homework deadline")
    if len(normalized_text) < 700 and sum(term in normalized_text for term in administrative_terms) >= 2:
        return True
    return False


COMPONENT_KINDS = Literal["explanation", "key_definition", "flow", "structure", "relationship_map", "comparison", "worked_example", "equation", "callout", "takeaway", "walkthrough"]
TeachingDepth = Literal["concise", "balanced", "detailed"]

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
    # Express the visual-label bound in JSON Schema as well as runtime
    # validation so the provider sees the same contract Claude is judged by.
    relation: str = Field(min_length=1, max_length=40, pattern=r"^\S+(?:\s+\S+){0,3}$")
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
    multiplicity: str | None = Field(default=None, max_length=40)
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
    structure_type: Literal["hierarchy", "architecture"] = Field(default="hierarchy", alias="structureType")
    connections: list[GraphEdge] = Field(default_factory=list, max_length=12)
    why_it_matters: str | None = Field(default=None, alias="whyItMatters")

    @model_validator(mode="after")
    def validate_architecture_links(self):
        seen: set[str] = set()
        def visit(node: TreeNode):
            if node.id in seen:
                raise ValueError("structure tree contains duplicate node IDs")
            seen.add(node.id)
            for child in node.children:
                visit(child)
        visit(self.root)
        if any(edge.source not in seen or edge.target not in seen for edge in self.connections):
            raise ValueError("structure connections must reference tree nodes")
        return self


class RelationshipMapComponent(_TypedComponent):
    kind: Literal["relationship_map"]
    nodes: list[GraphNode] = Field(min_length=2)
    edges: list[GraphEdge] = Field(min_length=1)
    why_it_matters: str | None = Field(default=None, alias="whyItMatters")

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


class WalkthroughComponent(_TypedComponent):
    """A contained, interactive learning experience rendered by the shared
    StepThroughMechanism shell. The mechanism remains semantic; geometry and
    controls stay owned by the trusted frontend renderer.
    """
    kind: Literal["walkthrough"]
    learning_goal: str = Field(alias="learningGoal", min_length=1, max_length=300)
    bottleneck: str = Field(min_length=1, max_length=240)
    mechanism: StepThroughMechanism
    estimated_minutes: int | None = Field(default=None, alias="estimatedMinutes", ge=1, le=60)


class GeneratedWalkthroughComponent(_TypedComponent):
    """Compact model-owned walkthrough; expanded deterministically after validation."""
    kind: Literal["walkthrough"]
    learning_goal: str = Field(alias="learningGoal", min_length=1, max_length=240)
    bottleneck: str = Field(min_length=1, max_length=180)
    mechanism: GeneratedStepThroughMechanism
    estimated_minutes: int | None = Field(default=None, alias="estimatedMinutes", ge=1, le=60)


TypedSectionComponent = Annotated[Union[
    ExplanationComponent, KeyDefinitionComponent, FlowComponent,
    StructureComponent, RelationshipMapComponent, ComparisonComponent,
    WorkedExampleComponent, EquationComponent, CalloutComponent,
    TakeawayComponent, WalkthroughComponent,
], Field(discriminator="kind")]
GeneratedTypedSectionComponent = Annotated[Union[
    ExplanationComponent, KeyDefinitionComponent, FlowComponent,
    StructureComponent, RelationshipMapComponent, ComparisonComponent,
    WorkedExampleComponent, EquationComponent, CalloutComponent,
    TakeawayComponent, GeneratedWalkthroughComponent,
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
    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    title: str
    big_idea: str = Field(alias="bigIdea")
    learning_goals: list[str] = Field(alias="learningGoals")
    components: list[GeneratedTypedSectionComponent]
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
    def sentences(value: str) -> list[str]:
        cleaned = " ".join(value.split())
        return [piece.strip() for piece in re.split(r"(?<=[.!?])\s+|\s*[•]\s*", cleaned) if piece.strip()]

    first_text = next((b.text.strip() for b in section.blocks if usable(b.text)), "")
    first_sentences = sentences(first_text)
    big_idea = (first_sentences[0] if first_sentences else first_text)[:320]
    components: list[SectionComponent] = []
    for block, obj in zip(section.blocks, [objects.get(b.id) for b in section.blocks]):
        if obj is None or not usable(block.text):
            continue
        kind = "explanation" if obj.type == "plain_text" else {"process": "flow", "causal": "flow", "hierarchy": "structure", "quantitative": "worked_example", "comparison": "comparison", "concept_map": "relationship_map"}.get(obj.type, "explanation")
        title = obj.title if usable(obj.title) else (section.title if usable(section.title) else "Explanation")
        compact_text = " ".join(sentences(block.text)[:3])[:600]
        data = {"kind": kind, "title": title, "text": compact_text, "sourceBlockIds": [block.id], "learningObject": obj}
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
                text=compact_text,
                sourceBlockIds=[block.id],
                learningObject=obj,
            ))
    title = section.title if usable(section.title) else (available[0].title if available else "Learning section")
    # Keep fallback takeaways genuinely memorable rather than repeating whole
    # source blocks.  Preserve the first sentence/line as a conservative,
    # source-grounded compression; never invent a summary.
    takeaways = []
    for block in section.blocks:
        if not usable(block.text):
            continue
        text = " ".join(block.text.split())
        takeaway = text.split(".", 1)[0].strip() if "." in text else text
        if takeaway and takeaway != big_idea and takeaway not in takeaways:
            takeaways.append(takeaway[:240])
        if len(takeaways) == 3:
            break
    return SectionNote(id=section.id, title=title, bigIdea=big_idea or title, learningGoals=["Understand the main idea and how the section's parts connect."], components=components, keyTakeaways=takeaways, sourceBlockIds=section.learning_block_ids)


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


def model_section_note(section: SectionInput, *, model_version: str = "section-v3-grounded", depth: TeachingDepth = "balanced") -> SectionNote:
    """Generate one coherent section note. The cache is process-local V1 and
    deliberately versioned so prompt/schema changes invalidate old results."""
    from app.services.anthropic_service import _run_structured_tool
    source = "\n\n".join(f"[{block.id}] {block.text}" for block in section.blocks)
    key = hashlib.sha256(f"{model_version}:{depth}:{section.title}:{source}".encode()).hexdigest()
    if key in _SECTION_CACHE:
        logger.info("section_generation_cache_hit section_id=%s title=%r model=claude-haiku-4-5-20251001", section.id, section.title)
        return _SECTION_CACHE[key].model_copy()
    schema = GeneratedSectionNote.model_json_schema(by_alias=True)
    started = time.perf_counter()
    logger.info("section_generation_start section_id=%s title=%r model=claude-haiku-4-5-20251001 depth=%s cache_hit=false source_chars=%d blocks=%d max_tokens=%d", section.id, section.title, depth, len(source), len(section.blocks), SECTION_NOTE_MAX_TOKENS)
    try:
        depth_instruction = {
            "concise": "Teaching depth: CONCISE STUDY GUIDE. Prefer the fewest components that preserve exam-relevant mechanisms, definitions, equations, and relationships; use terse phrases and minimal supporting prose.",
            "balanced": "Teaching depth: BALANCED. Include enough intuition to understand the central mechanism, with selective visuals, definitions, and examples.",
            "detailed": "Teaching depth: DETAILED EXPLANATION. Add grounded why/how reasoning and a walkthrough when it materially clarifies a difficult mechanism, but do not write an essay or repeat the source.",
        }[depth]
        prompt = ("Design a source-grounded learning experience for this coherent section; do not merely summarize or split the source into prose cards. "
                  + depth_instruction + " "
                  "First identify the central mental model and the conceptual bottleneck a learner must overcome. Then compose a short, coherent sequence "
                  "of only the components that materially improve understanding (usually 2–4 strong components; never emit every type by default). "
                  "SOURCE BOUNDARY: every factual claim, property, example, recommendation, and takeaway must be stated in the supplied blocks or follow by direct arithmetic from supplied values. "
                  "Do not add plausible background knowledge, design advice, examples, properties, or causes from memory. If the source does not explain why, omit that explanation. "
                  "Check numerical comparisons and arithmetic exactly; do not turn a derived result into a broader optimization claim. "
                  "Use an explanation only for ideas that are genuinely clearer as prose, adds information beyond bigIdea, and fits in 1–2 concise sentences. For a process, mechanism, or causal chain prefer a FLOW with 2+ concise nodes, "
                  "meaningful 1–3 word verb relations, putting any longer meaning in the edge explanation, and a separate brief explanation of why transitions matter. For a multi-stage mechanism whose state changes are clearer interactively, you may choose one WALKTHROUGH component using the supplied semantic mechanism contract; use it selectively, keep it to 2–5 meaningful stages, and never include coordinates or presentation code. For containment or levels prefer a connected STRUCTURE; set structureType to architecture only when repeated components, multiplicity, or cross-component connections are important, and use concise connections rather than inventing links. "
                  "with an explicit root and children. For equations or numerical reasoning prefer EQUATION or WORKED_EXAMPLE with variables, supplied values, ordered "
                  "substitution/derivation steps, result, and interpretation. For systems of concepts use a selective connected RELATIONSHIP_MAP (3–7 concepts) with "
                  "specific relations such as uses, maps, caches, contains, enables, or depends on; never use generic related to. Preserve technical terminology, mechanisms, "
                  "equations, units, and caveats supported by the source. Preserve actual graph topology: mutually exclusive outcomes branch from their decision node and must never be chained together. "
                  "Remove repetition and extraction noise. Keep labels concise. keyTakeaways should contain at most 2 distinct, source-supported conclusions and must not repeat bigIdea verbatim. "
                  "Every component must cite sourceBlockIds from the supplied blocks, and all required fields must be present. Return no fields outside the schema.\n\n" + source)
        raw = _run_structured_tool(prompt, "section_learning_note", schema, SECTION_NOTE_MAX_TOKENS, timeout=SECTION_NOTE_TIMEOUT_SECONDS, max_retries=0)
    except Exception as exc:
        logger.exception("section_generation_failure section_id=%s title=%r stage=anthropic_request exception_type=%s latency_ms=%.1f fallback=true", section.id, section.title, type(exc).__name__, (time.perf_counter() - started) * 1000)
        raise
    try:
        logger.info("section_generation_response section_id=%s title=%r top_level_keys=%s", section.id, section.title, sorted(raw.keys()) if isinstance(raw, dict) else [])
        generated = GeneratedSectionNote.model_validate(_normalize_generated_section_payload(raw))
        generated_payload = generated.model_dump(by_alias=True)
        for index, component in enumerate(generated_payload.get("components", [])):
            if component.get("kind") == "walkthrough":
                generated_component = generated.components[index]
                assert isinstance(generated_component, GeneratedWalkthroughComponent)
                component["mechanism"] = generated_component.mechanism.to_canonical().model_dump(by_alias=True)
        note = SectionNote.model_validate({**generated_payload, "id": section.id, "sourceBlockIds": section.learning_block_ids})
    except Exception as exc:
        logger.exception("section_generation_failure section_id=%s title=%r stage=section_note_validation exception_type=%s latency_ms=%.1f fallback=true", section.id, section.title, type(exc).__name__, (time.perf_counter() - started) * 1000)
        raise
    logger.info("section_generation_success section_id=%s title=%r model=claude-haiku-4-5-20251001 latency_ms=%.1f fallback=false components=%d", section.id, section.title, (time.perf_counter() - started) * 1000, len(note.components))
    _SECTION_CACHE[key] = note
    return note.model_copy()


async def generate_sections_concurrently(sections: list[SectionInput], objects: dict[str, LearningObject], *, concurrency: int = 3, use_model: bool = False, depth: TeachingDepth = "balanced") -> list[SectionNote]:
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def one(section: SectionInput) -> SectionNote:
        async with semaphore:
            if use_model:
                try:
                    return await asyncio.to_thread(model_section_note, section, depth=depth)
                except Exception as exc:
                    logger.warning("section_generation_fallback section_id=%s title=%r stage=section_task exception_type=%s fallback=true", section.id, section.title, type(exc).__name__)
                    pass
            return safe_deterministic_section_note(section, objects)

    return list(await asyncio.gather(*(one(section) for section in sections if not is_low_value_section(section))))

async def generate_sections_progressively(sections: list[SectionInput], objects: dict[str, LearningObject], on_complete, *, concurrency: int = 3, use_model: bool = False, depth: TeachingDepth = "balanced") -> list[SectionNote]:
    semaphore = asyncio.Semaphore(max(1, concurrency))
    active = [(index, section) for index, section in enumerate(sections) if not is_low_value_section(section)]
    results: list[SectionNote | None] = [None] * len(sections)

    async def one(index: int, section: SectionInput) -> None:
        async with semaphore:
            try:
                note = await asyncio.to_thread(model_section_note, section, depth=depth) if use_model else deterministic_section_note(section, objects)
            except Exception as exc:
                note = safe_deterministic_section_note(section, objects)
                logger.warning("section_generation_fallback section_id=%s title=%r stage=section_task exception_type=%s fallback=true", section.id, section.title, type(exc).__name__)
                await on_complete(index, note, str(exc))
            else:
                await on_complete(index, note, None)
            results[index] = note

    await asyncio.gather(*(one(index, section) for index, section in active))
    return [note for note in results if note is not None]
