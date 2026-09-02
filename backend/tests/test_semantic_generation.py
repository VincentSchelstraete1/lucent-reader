from types import SimpleNamespace

from app.semantic import DeterministicSemanticGenerator, assemble_note
from app.routing import RepresentationDecision

def block(text, ident="b1"):
    return SimpleNamespace(id=ident, text=text, title=None, source=SimpleNamespace(page_start=1, page_end=1, normalized_block_ids=["n1"], locations=[]))

def decision(kind, ident="b1"):
    return RepresentationDecision(learning_block_id=ident, type=kind, confidence=.8, method="deterministic", scores={kind: .8}, fallback_used=False)

def test_all_types_validate_and_plain_text_is_safe_fallback():
    generator = DeterministicSemanticGenerator()
    examples = {
        "process": "First connect. Then send data.",
        "comparison": "A is fast whereas B is small.",
        "causal": "Rain causes flooding, which leads to delays.",
        "concept_map": "Photosynthesis involves chlorophyll, sunlight, water, and glucose.",
        "hierarchy": "Memory consists of cache, RAM, and storage.",
        "quantitative": "Velocity = distance / time.",
        "plain_text": "A short description.",
    }
    for kind, text in examples.items():
        obj = generator.generate(block(text, kind), decision(kind, kind))
        assert obj.type == kind

def test_note_assembly_preserves_source_order_and_provenance():
    first, second = block("First connect. Then send data.", "a"), block("A is fast whereas B is small.", "b")
    decisions = {"a": decision("process", "a"), "b": decision("comparison", "b")}
    generator = DeterministicSemanticGenerator()
    objects = {b.id: generator.generate(b, decisions[b.id]) for b in (first, second)}
    note = assemble_note("lesson.pdf", "pdf", 2, [first, second], decisions, objects)
    assert [section.learning_block_id for section in note.sections] == ["a", "b"]
    assert note.sections[0].source["normalized_block_ids"] == ["n1"]
