from app.normalization.schema import NormalizedBlock, SourceReference
from app.routing import HybridRouterConfig, route_learning_block_hybrid, should_fallback
from app.routing.representation_types import RepresentationRoute
from app.segmentation import SegmentationMetadata, build_learning_block


def _route(type_: str, confidence: float) -> RepresentationRoute:
    scores = {t: 0.1 for t in ["plain_text", "process", "comparison", "causal", "concept_map", "hierarchy", "quantitative"]}
    scores[type_] = confidence
    return RepresentationRoute(type=type_, confidence=confidence, scores=scores, reasons=["test"])


def _learning_block(text: str, id: str = "learning-block-1"):
    constituent = NormalizedBlock(
        id="normalized-a", type="paragraph", text=text,
        source=SourceReference(page_start=1, page_end=1, raw_block_ids=["a"], bboxes=[]),
    )
    return build_learning_block(id, constituents=[constituent], block_type="section", segmentation=SegmentationMetadata(method="structural", boundary_reason="test"))


class StubClassifier:
    def __init__(self, result):
        self.result = result
        self.calls: list[str] = []

    def classify(self, text: str):
        self.calls.append(text)
        return self.result


def test_should_fallback_triggers_on_plain_text_by_default():
    assert should_fallback(_route("plain_text", 0.76)) is True


def test_should_fallback_does_not_trigger_on_a_structured_result_by_default():
    assert should_fallback(_route("process", 0.44)) is False


def test_should_fallback_respects_disabled_plain_text_trigger():
    config = HybridRouterConfig(trigger_on_plain_text=False)
    assert should_fallback(_route("plain_text", 0.76), config) is False


def test_should_fallback_minimum_structured_confidence_is_opt_in():
    low_confidence_structured = _route("process", 0.05)
    assert should_fallback(low_confidence_structured) is False  # off by default
    config = HybridRouterConfig(minimum_structured_confidence=0.4)
    assert should_fallback(low_confidence_structured, config) is True


def test_hybrid_uses_deterministic_decision_when_not_uncertain():
    block = _learning_block("First the CPU fetches. Next it decodes. Finally it executes.")
    classifier = StubClassifier("comparison")
    decision = route_learning_block_hybrid(block, classifier)
    assert decision.method == "deterministic"
    assert decision.fallback_used is False
    assert classifier.calls == []  # never invoked - deterministic was confident


def test_hybrid_invokes_classifier_when_deterministic_falls_back_to_plain_text():
    block = _learning_block("Cache memory is a small, fast memory located close to the processor.")
    classifier = StubClassifier("plain_text")
    decision = route_learning_block_hybrid(block, classifier)
    assert decision.method == "fallback_classifier"
    assert decision.fallback_used is True
    assert decision.confidence is None  # never a fabricated calibrated probability
    assert classifier.calls == [block.text]


def test_hybrid_safely_falls_back_to_deterministic_when_classifier_returns_none():
    block = _learning_block("Cache memory is a small, fast memory located close to the processor.")
    classifier = StubClassifier(None)
    decision = route_learning_block_hybrid(block, classifier)
    assert decision.method == "deterministic"
    assert decision.fallback_used is False
    assert decision.type == "plain_text"


def test_hybrid_treats_an_out_of_enum_classifier_result_as_failure():
    class MisbehavingClassifier:
        def classify(self, text):
            return "not_a_real_type"  # violates the ClassifierAdapter contract

    block = _learning_block("Cache memory is a small, fast memory located close to the processor.")
    decision = route_learning_block_hybrid(block, MisbehavingClassifier())
    assert decision.method == "deterministic"
    assert decision.type == "plain_text"
