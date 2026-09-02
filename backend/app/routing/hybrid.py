"""LearningBlock -> deterministic router -> [uncertain?] -> classifier
fallback -> RepresentationDecision. Deterministic routing stays the first
stage and is never replaced wholesale; the classifier is only consulted when
should_fallback() says so, and any classifier failure (timeout, error,
malformed output) safely reverts to the deterministic decision.
"""

from dataclasses import dataclass

from app.routing.classifier import ClassifierAdapter
from app.routing.representation_types import REPRESENTATION_TYPES, RepresentationDecision, RepresentationRoute
from app.routing.router import route_representation
from app.segmentation import LearningBlock


@dataclass(frozen=True)
class HybridRouterConfig:
    """Trigger signals, each independently toggleable/configurable.

    trigger_on_plain_text is enabled by default because it is the only
    evidence-justified signal found on the dev set: every deterministic
    "plain_text" prediction that turned out wrong was a case where a
    structured type was actually expected (39/39 dev failures), while every
    deterministic structured prediction was correct (33/33). Confidence and
    margin were both checked and rejected as trigger signals - on this dev
    set, INCORRECT predictions had higher average confidence (0.742) and
    margin (0.682) than correct ones (0.593 / 0.491), so "confidence below
    threshold" would not have caught these failures (see the Checkpoint F
    evaluation for the numbers). minimum_structured_confidence exists for a
    future low-confidence-structured-misclassification pattern, but is not
    currently evidence-justified, so it defaults to off.
    """

    trigger_on_plain_text: bool = True
    minimum_structured_confidence: float | None = None


def should_fallback(route: RepresentationRoute, config: HybridRouterConfig | None = None) -> bool:
    config = config or HybridRouterConfig()
    if config.trigger_on_plain_text and route.type == "plain_text":
        return True
    if (
        config.minimum_structured_confidence is not None
        and route.type != "plain_text"
        and route.confidence < config.minimum_structured_confidence
    ):
        return True
    return False


def _deterministic_decision(block_id: str, route: RepresentationRoute) -> RepresentationDecision:
    return RepresentationDecision(
        learning_block_id=block_id, type=route.type, confidence=route.confidence,
        method="deterministic", scores=route.scores, fallback_used=False,
    )


def route_learning_block_hybrid(
    block: LearningBlock,
    classifier: ClassifierAdapter,
    config: HybridRouterConfig | None = None,
) -> RepresentationDecision:
    route = route_representation(block.text)
    if not should_fallback(route, config):
        return _deterministic_decision(block.id, route)

    classified_type = classifier.classify(block.text)
    # Defense in depth: a well-behaved ClassifierAdapter only ever returns a
    # value from REPRESENTATION_TYPES or None (AnthropicClassifierAdapter
    # enforces this itself), but a third-party or future adapter might not -
    # treat anything outside the enum the same as a failed call.
    if classified_type is None or classified_type not in REPRESENTATION_TYPES:
        return _deterministic_decision(block.id, route)  # safe fallback on any classifier failure

    return RepresentationDecision(
        learning_block_id=block.id, type=classified_type, confidence=None,
        method="fallback_classifier", scores=route.scores, fallback_used=True,
    )
