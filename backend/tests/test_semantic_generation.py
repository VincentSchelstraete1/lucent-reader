from types import SimpleNamespace

from app.semantic import DeterministicSemanticGenerator, DeterministicPedagogicalPlanner, HybridSemanticGenerator, assemble_note
from app.routing import RepresentationDecision
from app.normalization import SourceReference

def block(text, ident="b1"):
    return SimpleNamespace(id=ident, text=text, title=None, heading_ancestry=[], attached_table_ids=[], attached_image_ids=[], source=SourceReference(page_start=1, page_end=1, raw_block_ids=["r1"], bboxes=[], locations=[]))

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
    assert note.sections[0].source["raw_block_ids"] == ["r1"]

def test_planner_explains_representation_purpose_and_can_downgrade_weak_map():
    planner = DeterministicPedagogicalPlanner()
    weak = planner.plan(block("The hippocampus is a brain structure.", "map"), decision("concept_map", "map"))
    assert weak.final_representation == "plain_text"
    strong = planner.plan(block("The TLB caches page-table translations.", "map2"), decision("concept_map", "map2"))
    assert strong.final_representation == "concept_map"
    assert strong.representation_plan

def test_hybrid_model_path_uses_one_combined_generation_call():
    calls = []
    class FakeModel:
        def generate_with_plan(self, current_block, current_decision, context):
            calls.append((current_block.id, current_decision.type))
            obj = DeterministicSemanticGenerator().generate(current_block, current_decision)
            plan = DeterministicPedagogicalPlanner().plan(current_block, current_decision, context)
            return plan, obj

    current = block("Rain causes flooding, which leads to delays.", "one-call")
    result = HybridSemanticGenerator(FakeModel()).generate_with_plan(current, decision("causal", "one-call"), None)
    assert result[1].type == "causal"
    assert calls == [("one-call", "causal")]
