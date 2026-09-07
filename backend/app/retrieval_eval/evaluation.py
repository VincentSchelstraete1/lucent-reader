from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Callable

from app.retrieval_eval.dataset import RetrievalEvalExample


@dataclass(frozen=True)
class RetrievalResult:
    ranked_block_ids: tuple[str, ...]
    answer_supported: bool
    latency_ms: float = 0.0


Strategy = Callable[[RetrievalEvalExample], RetrievalResult]


@dataclass(frozen=True)
class EvaluatedRetrieval:
    example: RetrievalEvalExample
    result: RetrievalResult
    recall_at_1: float | None
    recall_at_3: float | None
    recall_at_5: float | None
    reciprocal_rank: float | None
    complete_at_5: bool | None


@dataclass(frozen=True)
class RetrievalEvaluation:
    total: int
    supported: int
    unsupported: int
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    mrr: float
    complete_evidence_at_5: float
    false_support_rate: float
    correct_abstention_rate: float
    supported_false_refusal_rate: float
    p50_latency_ms: float
    p95_latency_ms: float
    failures: tuple[EvaluatedRetrieval, ...] = field(default_factory=tuple)
    rows: tuple[EvaluatedRetrieval, ...] = field(default_factory=tuple)


def _recall(example: RetrievalEvalExample, ranked: tuple[str, ...], k: int) -> float:
    selected = set(ranked[:k])
    return max(len(selected & group.block_ids) / len(group.block_ids) for group in example.gold)


def _reciprocal_rank(example: RetrievalEvalExample, ranked: tuple[str, ...]) -> float:
    relevant = set().union(*(group.block_ids for group in example.gold))
    for rank, block_id in enumerate(ranked, 1):
        if block_id in relevant:
            return 1.0 / rank
    return 0.0


def _complete(example: RetrievalEvalExample, ranked: tuple[str, ...], k: int) -> bool:
    selected = set(ranked[:k])
    return any(group.block_ids <= selected for group in example.gold)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * fraction + 0.5)))
    return ordered[index]


def evaluate_retrieval(examples: list[RetrievalEvalExample], strategy: Strategy) -> RetrievalEvaluation:
    rows: list[EvaluatedRetrieval] = []
    for example in examples:
        result = strategy(example)
        rows.append(EvaluatedRetrieval(
            example=example, result=result,
            recall_at_1=_recall(example, result.ranked_block_ids, 1) if example.supported else None,
            recall_at_3=_recall(example, result.ranked_block_ids, 3) if example.supported else None,
            recall_at_5=_recall(example, result.ranked_block_ids, 5) if example.supported else None,
            reciprocal_rank=_reciprocal_rank(example, result.ranked_block_ids) if example.supported else None,
            complete_at_5=_complete(example, result.ranked_block_ids, 5) if example.supported else None,
        ))
    supported = [row for row in rows if row.example.supported]
    unsupported = [row for row in rows if not row.example.supported]
    failures = [row for row in rows if (row.example.supported and (row.recall_at_5 or 0) < 1) or (not row.example.supported and row.result.answer_supported)]
    latencies = [row.result.latency_ms for row in rows]
    return RetrievalEvaluation(
        total=len(rows), supported=len(supported), unsupported=len(unsupported),
        recall_at_1=_mean([row.recall_at_1 or 0 for row in supported]),
        recall_at_3=_mean([row.recall_at_3 or 0 for row in supported]),
        recall_at_5=_mean([row.recall_at_5 or 0 for row in supported]),
        mrr=_mean([row.reciprocal_rank or 0 for row in supported]),
        complete_evidence_at_5=_mean([1.0 if row.complete_at_5 else 0.0 for row in supported]),
        false_support_rate=_mean([1.0 if row.result.answer_supported else 0.0 for row in unsupported]),
        correct_abstention_rate=_mean([0.0 if row.result.answer_supported else 1.0 for row in unsupported]),
        supported_false_refusal_rate=_mean([0.0 if row.result.answer_supported else 1.0 for row in supported]),
        p50_latency_ms=median(latencies) if latencies else 0.0,
        p95_latency_ms=_percentile(latencies, 0.95), failures=tuple(failures), rows=tuple(rows),
    )


def compare_failures(baseline: RetrievalEvaluation, candidate: RetrievalEvaluation) -> dict[str, list[str]]:
    before = {row.example.id for row in baseline.failures}
    after = {row.example.id for row in candidate.failures}
    return {"fixed": sorted(before - after), "regressions": sorted(after - before)}
