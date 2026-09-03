from app.normalization import SourceReference
from app.semantic import deterministic_section_note, group_learning_blocks
from app.semantic.section_notes import SectionInput
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
