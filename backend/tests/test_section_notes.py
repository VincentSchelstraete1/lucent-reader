import asyncio
import pytest

from app.normalization import SourceReference
from app.semantic import deterministic_section_note, group_learning_blocks, generate_sections_progressively
from app.semantic.section_notes import SectionInput
from app.semantic.section_notes import SectionComponent
from app.semantic import DeterministicSemanticGenerator
from app.routing import RepresentationDecision
from app.segmentation import LearningBlock
from app.semantic.section_notes import model_section_note, GeneratedSectionNote
from app.semantic.schema import CausalObject


def make_block(ident, text, ancestry=None):
    return LearningBlock(id=ident, block_type="section", text=text, character_count=len(text), normalized_block_ids=[], source=SourceReference(page_start=1, page_end=1, raw_block_ids=[ident], bboxes=[], locations=[]), segmentation={"method": "test", "boundaryReason": "test"}, title=None, heading_ancestry=ancestry or ["Caches"], attached_table_ids=[], attached_image_ids=[], token_count=None)


def test_grouping_preserves_order_and_heading_boundaries():
    blocks = [make_block("a", "One"), make_block("b", "Two"), make_block("c", "Three", ["Memory"])]
    sections = group_learning_blocks(blocks)
    assert [section.learning_block_ids for section in sections] == [["a", "b"], ["c"]]


def test_deterministic_section_note_preserves_component_provenance():
    block = make_block("a", "First connect. Then send data.")
    obj = DeterministicSemanticGenerator().generate(block, RepresentationDecision(learning_block_id="a", type="process", confidence=.8, method="deterministic", scores={}, fallback_used=False))
    note = deterministic_section_note(SectionInput("s", "Caches", ["Caches"], ["a"], [block], {}), {"a": obj})
    assert note.components[0].source_block_ids == ["a"]
    assert note.components[0].learning_object.type == "process"

def test_progressive_generation_reports_each_section_independently():
    first = make_block("a", "First connect. Then send data.")
    second = make_block("b", "A short explanation.")
    sections = group_learning_blocks([first, second], max_blocks=1)
    objects = {}
    completed = []

    async def on_complete(index, note, error):
        completed.append((index, note.id, error))

    notes = asyncio.run(generate_sections_progressively(sections, objects, on_complete, concurrency=2, use_model=False))
    assert [note.id for note in notes] == ["section-0", "section-1"]
    assert {item[0] for item in completed} == {0, 1}

def test_structured_components_reject_orphan_relationships_and_accept_definitions():
    with pytest.raises(ValueError):
        SectionComponent(kind="flow", title="Broken", sourceBlockIds=["a"], nodes=[{"id": "a", "label": "A"}], edges=[{"source": "a", "target": "missing", "relation": "causes"}])
    definition = SectionComponent(kind="key_definition", title="TLB", term="TLB", definition="Caches recent translations.", sourceBlockIds=["a"])
    assert definition.definition

def test_model_section_failure_isolated_to_deterministic_fallback(monkeypatch):
    block = make_block("failure", "A short section that should remain readable.")
    section = SectionInput("section-failure", "Failure", ["Failure"], [block.id], [block], {})
    def fail(*args, **kwargs):
        raise RuntimeError("provider unavailable")
    monkeypatch.setattr("app.services.anthropic_service._run_structured_tool", fail)
    with pytest.raises(RuntimeError):
        model_section_note(section, model_version="test-failure")


def test_section_request_uses_bounded_output_and_no_retries(monkeypatch):
    block = make_block("policy", "A short section.")
    section = SectionInput("section-policy", "Policy", [], [block.id], [block], {})
    seen = {}

    args_seen = []
    def fail(*args, **kwargs):
        args_seen.extend(args)
        seen.update(kwargs)
        raise RuntimeError("probe")

    monkeypatch.setattr("app.services.anthropic_service._run_structured_tool", fail)
    with pytest.raises(RuntimeError):
        model_section_note(section, model_version="test-policy")
    assert seen["max_retries"] == 0
    assert seen["timeout"] == 15
    assert args_seen[3] == 800


def test_model_structure_without_root_is_rejected(monkeypatch):
    block = make_block("structure", "Memory contains cache.")
    section = SectionInput("section-structure", "Memory", ["Memory"], [block.id], [block], {})

    def malformed(*args, **kwargs):
        return {
            "title": "Memory",
            "bigIdea": "Memory is organized into levels.",
            "learningGoals": [],
            "components": [{"kind": "structure", "title": "Levels", "sourceBlockIds": [block.id]}],
            "keyTakeaways": [],
            "omittedNoise": [],
        }

    monkeypatch.setattr("app.services.anthropic_service._run_structured_tool", malformed)
    with pytest.raises(ValueError, match="root"):
        model_section_note(section, model_version="test-missing-root")


@pytest.mark.parametrize("component", [
    {"kind": "explanation", "title": "Explain", "text": "Text", "sourceBlockIds": ["b"]},
    {"kind": "key_definition", "title": "Term", "term": "Term", "definition": "Meaning", "sourceBlockIds": ["b"]},
    {"kind": "flow", "title": "Flow", "nodes": [{"id": "a"}], "edges": [{"source": "a", "target": "a"}], "sourceBlockIds": ["b"]},
    {"kind": "structure", "title": "Tree", "root": {"id": "r"}, "sourceBlockIds": ["b"]},
    {"kind": "relationship_map", "title": "Map", "nodes": [{"id": "a"}], "edges": [{"source": "a", "target": "a"}], "sourceBlockIds": ["b"]},
    {"kind": "comparison", "title": "Compare", "items": [{"name": "A"}], "sourceBlockIds": ["b"]},
    {"kind": "worked_example", "title": "Example", "steps": [{"description": "Step"}], "sourceBlockIds": ["b"]},
    {"kind": "equation", "title": "Equation", "equation": "x = 1", "sourceBlockIds": ["b"]},
    {"kind": "callout", "title": "Note", "text": "Important", "sourceBlockIds": ["b"]},
    {"kind": "takeaway", "title": "Remember", "takeaway": "Key point", "sourceBlockIds": ["b"]},
])
def test_generated_section_note_accepts_minimum_valid_component(component):
    note = GeneratedSectionNote.model_validate({
        "title": "Section", "bigIdea": "Idea", "learningGoals": [],
        "components": [component], "keyTakeaways": [], "omittedNoise": [],
    })
    assert note.components[0].kind == component["kind"]


def test_generated_schema_requires_kind_specific_fields():
    schema = GeneratedSectionNote.model_json_schema(by_alias=True)
    serialized = str(schema)
    assert "GeneratedStructure" in serialized
    assert "root" in serialized
    assert "GeneratedDefinition" in serialized
    assert "term" in serialized and "definition" in serialized


def test_deterministic_fallback_downgrades_invalid_visual_to_explanation():
    block = make_block("causal", "A cache miss requires main memory access.")
    obj = CausalObject(
        id="causal", type="causal", title="Cache miss", learningGoal="Understand misses",
        sourceText=block.text, nodes=[{"id": "a", "label": "Cache miss"}], edges=[]
    )
    note = deterministic_section_note(SectionInput("s", "Cache", ["Cache"], [block.id], [block], {}), {block.id: obj})
    assert note.components[0].kind == "explanation"
    assert note.components[0].source_block_ids == [block.id]


def test_model_failure_then_fallback_produces_valid_section_note(monkeypatch):
    block = make_block("fallback", "A short section that remains readable.")
    section = SectionInput("section-fallback", "Fallback", ["Fallback"], [block.id], [block], {})
    obj = CausalObject(
        id=block.id, type="causal", title="Fallback", learningGoal="Understand",
        sourceText=block.text, nodes=[{"id": "a", "label": "A"}], edges=[]
    )
    monkeypatch.setattr("app.services.anthropic_service._run_structured_tool", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("provider unavailable")))
    objects = {block.id: obj}
    completed = []

    async def on_complete(index, note, error):
        completed.append((note, error))

    notes = asyncio.run(generate_sections_progressively([section], objects, on_complete, concurrency=1, use_model=True))
    assert len(notes) == 1
    assert notes[0].components[0].kind == "explanation"
    assert completed[0][1] == "provider unavailable"
