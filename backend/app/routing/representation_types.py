from dataclasses import dataclass, field
from typing import Literal


REPRESENTATION_TYPES = ["plain_text", "process", "comparison", "causal", "concept_map", "hierarchy", "quantitative"]
RepresentationType = Literal["plain_text", "process", "comparison", "causal", "concept_map", "hierarchy", "quantitative"]


@dataclass(frozen=True)
class RepresentationRoute:
    type: RepresentationType
    confidence: float
    scores: dict[str, float]
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RepresentationDecision:
    """Router output attached to one LearningBlock. Existing taxonomy only -
    routing never invents a new representation type, and this carries no
    LearningObject, Mermaid, or rendering detail (see architecture rules)."""

    learning_block_id: str
    type: RepresentationType
    confidence: float
    method: Literal["deterministic", "fallback_classifier"]
    scores: dict[str, float]
    fallback_used: bool = False
