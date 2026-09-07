"""Direct port of web/src/learning/routing/representationRouter.ts. Scoring
logic, weights, and control flow are ported line-for-line; only language
idioms differ (JS Math.round rounds half-away-from-zero, replicated in
_rounded below rather than relying on Python's banker's-rounding builtin).
"""

import math
import re

from app.routing.representation_types import REPRESENTATION_TYPES, RepresentationDecision, RepresentationRoute
from app.routing.scoring_config import ROUTER_CONFIG, ROUTER_MARKERS, STRUCTURED_TYPE_PRIORITY
from app.segmentation import LearningBlock


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _rounded(value: float, precision: int = ROUTER_CONFIG["scorePrecision"]) -> float:
    scale = 10**precision
    return math.floor(_clamp(value) * scale + 0.5) / scale


def _count(text: str, pattern: re.Pattern) -> int:
    return len(pattern.findall(text))


def _comma_separated_items(text: str) -> bool:
    return _count(text, re.compile(",")) >= 2


def _process_score(text: str) -> tuple[float, list[str]]:
    markers = ROUTER_MARKERS["process"]
    config = ROUTER_CONFIG["process"]
    transitions = _count(text, markers["transitions"])
    temporal = _count(text, markers["temporal"])
    explicit = bool(markers["explicit"].search(text))
    ordered_items = _count(text, markers["orderedItem"])
    arrows = bool(markers["arrow"].search(text))

    score = min(config["transitionCap"], transitions * config["transitionWeight"])
    score += min(config["temporalCap"], temporal * config["temporalWeight"])
    if transitions >= 2:
        score += config["repeatedTransitionBonus"]
    if explicit:
        score += config["explicitPhraseWeight"]
    if ordered_items >= 2:
        score += config["orderedListWeight"]
    elif ordered_items == 1:
        score += config["singleOrderedItemWeight"]
    if arrows:
        score += config["arrowWeight"]

    reasons = []
    if transitions:
        reasons.append("contains sequential transition words")
    if temporal or explicit:
        reasons.append("contains ordered procedural language")
    if ordered_items:
        reasons.append("contains numbered or ordered steps")
    if arrows:
        reasons.append("contains explicit progression arrows")
    return _rounded(score), reasons


def _comparison_score(text: str) -> tuple[float, list[str]]:
    markers = ROUTER_MARKERS["comparison"]
    config = ROUTER_CONFIG["comparison"]
    explicit_terms = 0 if markers["metaLanguage"].search(text) else _count(text, markers["explicit"])
    parallel = bool(markers["parallel"].search(text))
    comparative = bool(markers["comparative"].search(text))

    score = explicit_terms * config["explicitTermWeight"]
    score += config["parallelLanguageWeight"] if parallel else 0
    score += config["comparativeFormWeight"] if comparative else 0

    reasons = []
    if explicit_terms:
        reasons.append("contains explicit comparison language")
    if parallel:
        reasons.append("contrasts parallel alternatives")
    if comparative:
        reasons.append("uses a comparative relationship")
    return _rounded(score), reasons


def _causal_score(text: str) -> tuple[float, list[str]]:
    markers = ROUTER_MARKERS["causal"]
    config = ROUTER_CONFIG["causal"]
    directional = _count(text, markers["directional"])
    connectives = 0 if markers["metaLanguage"].search(text) else _count(text, markers["connective"])
    signal_count = directional + connectives
    has_two_clause_connection = connectives > 0 and bool(re.search(r"[,;]|\b(?:which|so)\b", text, re.IGNORECASE))

    score = directional * config["directionalWeight"] + connectives * config["connectiveWeight"]
    if has_two_clause_connection:
        score += config["twoClauseBonus"]
    if signal_count >= 2:
        score += config["repeatedSignalBonus"]

    reasons = []
    if directional:
        reasons.append("states a directional cause-and-effect relationship")
    if connectives:
        reasons.append("connects a cause with its consequence")
    if signal_count >= 2:
        reasons.append("contains multiple reinforcing causal signals")
    return _rounded(score), reasons


def _concept_map_score(text: str) -> tuple[float, list[str]]:
    markers = ROUTER_MARKERS["conceptMap"]
    config = ROUTER_CONFIG["conceptMap"]
    relations = _count(text, markers["relation"])
    hubs = _count(text, markers["hub"])
    entity_network = (relations > 0 or hubs > 0) and _comma_separated_items(text)
    combined_network = relations + hubs >= 2 or (relations > 0 and entity_network)

    score = relations * config["relationWeight"] + hubs * config["hubWeight"]
    if entity_network:
        score += config["entityNetworkWeight"]
    if combined_network:
        score += config["networkCombinationBonus"]

    reasons = []
    if relations:
        reasons.append("links concepts with explicit relationships")
    if hubs:
        reasons.append("describes a concept involving neighboring concepts")
    if entity_network:
        reasons.append("connects a network of multiple named concepts")
    return _rounded(score), reasons


def _hierarchy_score(text: str) -> tuple[float, list[str]]:
    markers = ROUTER_MARKERS["hierarchy"]
    config = ROUTER_CONFIG["hierarchy"]
    strong_containment = _count(text, markers["strongContainment"])
    weak_containment = _count(text, markers["weakContainment"])
    list_items = _count(text, markers["listItem"])
    nested_list = bool(markers["nestedListItem"].search(text))
    enumeration = (strong_containment + weak_containment > 0) and (
        _comma_separated_items(text) or bool(re.search(r":\s*[^.!?]+(?:,|;)", text))
    )

    score = strong_containment * config["strongContainmentWeight"] + weak_containment * config["weakContainmentWeight"]
    if enumeration:
        score += config["groupedEnumerationWeight"]
    if list_items >= 3:
        score += config["flatListWeight"]
    if nested_list:
        score += config["nestedListBonus"]

    reasons = []
    if strong_containment or weak_containment:
        reasons.append("contains explicit part-to-whole language")
    if enumeration:
        reasons.append("groups several members under a parent concept")
    if list_items >= 3:
        reasons.append("contains a structured list of members")
    if nested_list:
        reasons.append("contains nested hierarchy levels")
    return _rounded(score), reasons


def _quantitative_score(text: str) -> tuple[float, list[str]]:
    markers = ROUTER_MARKERS["quantitative"]
    config = ROUTER_CONFIG["quantitative"]
    equation = bool(markers["symbolicEquation"].search(text))
    verbal_relationship = bool(markers["verbalRelationship"].search(text))
    percentages = _count(text, markers["percentage"])
    units = _count(text, markers["unit"])
    quantities = _count(text, markers["quantity"])

    score = config["symbolicEquationWeight"] if equation else 0
    if verbal_relationship:
        score += config["verbalRelationshipWeight"]
    if percentages:
        score += config["percentageWeight"]
    if units:
        score += config["unitWeight"]
    if quantities >= 2:
        score += config["multipleQuantityWeight"]

    reasons = []
    if equation:
        reasons.append("contains a symbolic mathematical relationship")
    if verbal_relationship:
        reasons.append("describes a quantitative relationship in words")
    if percentages or units:
        reasons.append("contains explicit quantities or units")
    if quantities >= 2:
        reasons.append("relates multiple numeric values")
    return _rounded(score), reasons


_SCORERS = {
    "process": _process_score,
    "comparison": _comparison_score,
    "causal": _causal_score,
    "concept_map": _concept_map_score,
    "hierarchy": _hierarchy_score,
    "quantitative": _quantitative_score,
}


def route_representation(source_text: str) -> RepresentationRoute:
    text = source_text.strip()
    signals = {type_: _SCORERS[type_](text) for type_ in _SCORERS}

    strongest = STRUCTURED_TYPE_PRIORITY[0]
    for type_ in STRUCTURED_TYPE_PRIORITY[1:]:
        if signals[type_][0] > signals[strongest][0]:
            strongest = type_
    strongest_score = signals[strongest][0]

    plain_config = ROUTER_CONFIG["plainText"]
    if strongest_score < ROUTER_CONFIG["structuredThreshold"]:
        plain_score = _rounded(max(plain_config["minimumConfidence"], plain_config["baseConfidence"] - strongest_score * plain_config["competingSignalPenalty"]))
    else:
        plain_score = plain_config["structuredContextScore"]

    scores = {type_: (plain_score if type_ == "plain_text" else signals[type_][0]) for type_ in REPRESENTATION_TYPES}

    if not text or strongest_score < ROUTER_CONFIG["structuredThreshold"]:
        return RepresentationRoute(type="plain_text", confidence=plain_score, scores=scores, reasons=["no strong structural signals detected"])
    return RepresentationRoute(type=strongest, confidence=strongest_score, scores=scores, reasons=signals[strongest][1])


# Alias used by the reproducible experiment/evaluation harness to name the frozen baseline.
route_representation_baseline = route_representation


def route_learning_block(block: LearningBlock) -> RepresentationDecision:
    route = route_representation(block.text)
    return RepresentationDecision(
        learning_block_id=block.id,
        type=route.type,
        confidence=route.confidence,
        method="deterministic",
        scores=route.scores,
        fallback_used=False,
    )
