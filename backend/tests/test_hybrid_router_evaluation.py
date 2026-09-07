"""Replays a real, recorded live-Anthropic-API evaluation run (captured once
via scripts/evaluate_hybrid_router.py against the router dataset's untouched
holdout split - see tests/fixtures/hybrid_router_holdout_recording.json) so
the wiring is verified in the automated suite without live API calls (costly,
slow, non-deterministic) on every test run. The recorded numbers themselves
are the real evidence behind the Checkpoint F promotion decision - see the
final report for the full comparison and the decision-gate reasoning.
"""

import json
from pathlib import Path

from app.routing.dataset import split_router_dataset
from app.routing.hybrid import route_learning_block_hybrid, should_fallback
from app.routing.router import route_representation
from app.segmentation import SegmentationMetadata, build_learning_block
from app.normalization.schema import NormalizedBlock, SourceReference

_RECORDING_PATH = Path(__file__).resolve().parent / "fixtures" / "hybrid_router_holdout_recording.json"


class _ReplayClassifier:
    """Returns the exact response the real Anthropic API gave for each text,
    recorded once - never calls the network."""

    def __init__(self, recording: dict[str, str | None]) -> None:
        self._recording = recording

    def classify(self, text: str) -> str | None:
        return self._recording[text]


def _learning_block(example_id: str, text: str):
    constituent = NormalizedBlock(
        id=f"normalized-{example_id}", type="paragraph", text=text,
        source=SourceReference(page_start=1, page_end=1, raw_block_ids=[example_id], bboxes=[]),
    )
    return build_learning_block(
        f"learning-block-{example_id}", constituents=[constituent], block_type="section",
        segmentation=SegmentationMetadata(method="structural", boundary_reason="test"),
    )


def _load_recording():
    data = json.loads(_RECORDING_PATH.read_text())
    holdout = {example.id: example for example in split_router_dataset()["holdout"] if not example.ambiguous}
    by_text = {holdout[row["id"]].text: row["classifier"] for row in data["rows"]}
    return data, holdout, by_text


def test_recorded_holdout_run_shows_no_regressions_and_a_large_accuracy_gain():
    data, _holdout, _by_text = _load_recording()
    assert data["deterministic_only_accuracy"] == 0.6429
    assert data["hybrid_accuracy"] == 0.9643
    assert data["regressions"] == []
    assert data["fallback_rate"] == 0.5
    assert data["deterministic_subset_accuracy"] == 1.0  # every non-fallback decision was correct


def test_replaying_the_recording_through_the_real_hybrid_wiring_reproduces_it():
    data, holdout, by_text = _load_recording()
    classifier = _ReplayClassifier(by_text)

    reproduced_correct = 0
    reproduced_regressions = []
    for row in data["rows"]:
        example = holdout[row["id"]]
        block = _learning_block(example.id, example.text)
        decision = route_learning_block_hybrid(block, classifier)
        assert decision.fallback_used == row["fallback_triggered"]
        assert decision.type == row["hybrid"]
        reproduced_correct += decision.type == example.expected
        deterministic_type = route_representation(example.text).type
        if deterministic_type == example.expected and decision.type != example.expected:
            reproduced_regressions.append(example.id)

    assert round(reproduced_correct / len(data["rows"]), 4) == data["hybrid_accuracy"]
    assert reproduced_regressions == []


def test_deterministic_coverage_examples_never_reach_the_classifier():
    data, holdout, by_text = _load_recording()
    classifier = _ReplayClassifier(by_text)
    for row in data["rows"]:
        if row["fallback_triggered"]:
            continue
        example = holdout[row["id"]]
        route = route_representation(example.text)
        assert should_fallback(route) is False
