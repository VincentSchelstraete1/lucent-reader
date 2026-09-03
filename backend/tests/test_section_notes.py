import asyncio
import pytest

from app.normalization import SourceReference
from app.semantic import deterministic_section_note, group_learning_blocks, generate_sections_progressively
from app.semantic.section_notes import SectionInput
from app.semantic.section_notes import SectionComponent
from app.semantic import DeterministicSemanticGenerator
from app.routing import RepresentationDecision
from app.segmentation import LearningBlock


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
