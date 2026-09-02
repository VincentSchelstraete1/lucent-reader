"""Direct port of web/src/learning/routing/evaluation/evaluationMetrics.ts."""

from dataclasses import dataclass, field
from typing import Callable

from app.routing.dataset import RouterExample
from app.routing.representation_types import REPRESENTATION_TYPES, RepresentationRoute


RouterFunction = Callable[[str], RepresentationRoute]


@dataclass(frozen=True)
class EvaluatedExample:
    example: RouterExample
    predicted: str
    confidence: float
    scores: dict[str, float]
    reasons: list[str]
    strict_correct: bool
    acceptable: bool


@dataclass(frozen=True)
class ConfidenceStats:
    min: float
    mean: float
    max: float


@dataclass(frozen=True)
class EvaluationSummary:
    total: int
    correct: int
    accuracy: float
    per_class: dict[str, dict[str, float]]
    confusion: dict[str, dict[str, int]]
    correct_confidence: ConfidenceStats
    incorrect_confidence: ConfidenceStats
    failures: list[EvaluatedExample]
    ambiguous: list[EvaluatedExample] = field(default_factory=list)


def _rounded(value: float, precision: int = 3) -> float:
    return round(value, precision)


def _confidence_stats(values: list[float]) -> ConfidenceStats:
    if not values:
        return ConfidenceStats(0.0, 0.0, 0.0)
    return ConfidenceStats(min(values), _rounded(sum(values) / len(values)), max(values))


def evaluate_router(examples: list[RouterExample], router: RouterFunction) -> EvaluationSummary:
    evaluated: list[EvaluatedExample] = []
    for example in examples:
        result = router(example.text)
        acceptable_types = example.acceptable_types or [example.expected]
        evaluated.append(
            EvaluatedExample(
                example=example,
                predicted=result.type,
                confidence=result.confidence,
                scores=result.scores,
                reasons=result.reasons,
                strict_correct=result.type == example.expected,
                acceptable=result.type in acceptable_types,
            )
        )

    strict = [item for item in evaluated if not item.example.ambiguous]
    correct = [item for item in strict if item.strict_correct]
    incorrect = [item for item in strict if not item.strict_correct]

    per_class: dict[str, dict[str, float]] = {}
    confusion: dict[str, dict[str, int]] = {}
    for expected_type in REPRESENTATION_TYPES:
        class_examples = [item for item in strict if item.example.expected == expected_type]
        class_correct = [item for item in class_examples if item.strict_correct]
        per_class[expected_type] = {
            "correct": len(class_correct),
            "total": len(class_examples),
            "accuracy": _rounded(len(class_correct) / len(class_examples)) if class_examples else 0.0,
        }
        confusion[expected_type] = {
            predicted_type: len([item for item in strict if item.example.expected == expected_type and item.predicted == predicted_type])
            for predicted_type in REPRESENTATION_TYPES
        }

    return EvaluationSummary(
        total=len(strict),
        correct=len(correct),
        accuracy=_rounded(len(correct) / len(strict)) if strict else 0.0,
        per_class=per_class,
        confusion=confusion,
        correct_confidence=_confidence_stats([item.confidence for item in correct]),
        incorrect_confidence=_confidence_stats([item.confidence for item in incorrect]),
        failures=incorrect,
        ambiguous=[item for item in evaluated if item.example.ambiguous],
    )


@dataclass(frozen=True)
class EvaluationChanges:
    fixed: list[str]
    regressions: list[str]


def compare_evaluations(baseline: EvaluationSummary, candidate: EvaluationSummary) -> EvaluationChanges:
    baseline_failures = {item.example.id for item in baseline.failures}
    candidate_failures = {item.example.id for item in candidate.failures}
    return EvaluationChanges(
        fixed=sorted(baseline_failures - candidate_failures),
        regressions=sorted(candidate_failures - baseline_failures),
    )
