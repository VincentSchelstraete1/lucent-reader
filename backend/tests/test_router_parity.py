from app.routing.dataset import DATASET_SPLIT_SEED, load_router_dataset, split_router_dataset
from app.routing.evaluation import evaluate_router
from app.routing.router import route_representation_baseline


def test_shared_dataset_loads_with_the_same_shape_ts_expects():
    dataset = load_router_dataset()
    assert len(dataset) == 126
    assert len({example.id for example in dataset}) == len(dataset)


def test_split_matches_ts_partition_sizes_exactly():
    # web/src/learning/routing/evaluation/routerDataset.test.ts asserts these
    # same numbers (91/35) against the identical JSON file - a mismatch here
    # would mean stable_hash's FNV-1a port has diverged from JS's Math.imul
    # behavior.
    assert DATASET_SPLIT_SEED == "lucent-router-evaluation-v1"
    split = split_router_dataset()
    assert len(split["development"]) == 91
    assert len(split["holdout"]) == 35


def test_dev_accuracy_matches_ts_frozen_baseline():
    # web/src/learning/routing/evaluation/runDevelopmentBaseline.test.ts
    # asserts {correct: 45, total: 84, accuracy: 0.536} against the same
    # dataset and the same (frozen, untuned) deterministic scoring logic.
    split = split_router_dataset()
    summary = evaluate_router(split["development"], route_representation_baseline)
    assert (summary.correct, summary.total, summary.accuracy) == (45, 84, 0.536)


def test_holdout_accuracy_matches_ts_frozen_baseline():
    # web/src/learning/routing/evaluation/runFinalHoldout.test.ts asserts
    # {correct: 18, total: 28, accuracy: 0.643} for the same baseline router.
    split = split_router_dataset()
    summary = evaluate_router(split["holdout"], route_representation_baseline)
    assert (summary.correct, summary.total, summary.accuracy) == (18, 28, 0.643)
