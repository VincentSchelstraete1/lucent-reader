from dataclasses import dataclass

from app.normalization.schema import NormalizedDocument
from app.segmentation.schema import LearningBlock


@dataclass(frozen=True)
class SegmentationExample:
    """One hand-labeled document. `expected_starts` is the set of
    NormalizedBlock ids that SHOULD open a new LearningBlock, excluding the
    document's very first block (whose boundary is trivially always true for
    every strategy and therefore uninformative)."""

    id: str
    category: str
    document: NormalizedDocument
    expected_starts: set[str]


def all_normalized_block_ids(document: NormalizedDocument) -> list[str]:
    return [block.id for page in document.pages for block in page.blocks]


def predicted_starts(blocks: list[LearningBlock], document: NormalizedDocument) -> set[str]:
    first_block_id = all_normalized_block_ids(document)[0]
    return {block.normalized_block_ids[0] for block in blocks if block.normalized_block_ids} - {first_block_id}


@dataclass(frozen=True)
class SegmentationMetrics:
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    over_segmentation_rate: float  # fraction of predicted boundaries that were wrong (1 - precision)
    under_segmentation_rate: float  # fraction of true boundaries missed (1 - recall)
    average_block_characters: float
    block_count: int


def _rounded(value: float) -> float:
    return round(value, 4)


def evaluate_segmentation(
    examples: list[SegmentationExample],
    strategy,
) -> SegmentationMetrics:
    total_tp = total_fp = total_fn = 0
    total_characters = 0
    total_blocks = 0
    for example in examples:
        blocks = strategy(example.document)
        predicted = predicted_starts(blocks, example.document)
        expected = example.expected_starts
        total_tp += len(predicted & expected)
        total_fp += len(predicted - expected)
        total_fn += len(expected - predicted)
        total_characters += sum(block.character_count for block in blocks)
        total_blocks += len(blocks)

    predicted_count = total_tp + total_fp
    expected_count = total_tp + total_fn
    precision = (total_tp / predicted_count) if predicted_count else (1.0 if not expected_count else 0.0)
    recall = (total_tp / expected_count) if expected_count else (1.0 if not predicted_count else 0.0)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return SegmentationMetrics(
        true_positives=total_tp,
        false_positives=total_fp,
        false_negatives=total_fn,
        precision=_rounded(precision),
        recall=_rounded(recall),
        f1=_rounded(f1),
        over_segmentation_rate=_rounded(1 - precision),
        under_segmentation_rate=_rounded(1 - recall),
        average_block_characters=_rounded(total_characters / total_blocks) if total_blocks else 0.0,
        block_count=total_blocks,
    )


@dataclass(frozen=True)
class QualitativeCase:
    example_id: str
    kind: str  # "correct_grouping" | "false_split" | "missed_split" | "giant_block" | "tiny_block"
    description: str


def qualitative_examples(examples: list[SegmentationExample], strategy) -> list[QualitativeCase]:
    cases: list[QualitativeCase] = []
    for example in examples:
        blocks = strategy(example.document)
        predicted = predicted_starts(blocks, example.document)
        expected = example.expected_starts
        for false_start in sorted(predicted - expected):
            cases.append(QualitativeCase(example.id, "false_split", f"Predicted an unexpected boundary before '{false_start}'."))
        for missed in sorted(expected - predicted):
            cases.append(QualitativeCase(example.id, "missed_split", f"Missed the expected boundary before '{missed}'."))
        for block in blocks:
            if block.character_count > 2000:
                cases.append(QualitativeCase(example.id, "giant_block", f"{block.id} is {block.character_count} characters."))
            elif 0 < block.character_count < 30 and block.block_type != "figure":
                cases.append(QualitativeCase(example.id, "tiny_block", f"{block.id} is only {block.character_count} characters: {block.text!r}"))
        if predicted == expected and predicted:
            cases.append(QualitativeCase(example.id, "correct_grouping", f"All {len(expected)} expected boundaries matched exactly."))
    return cases
