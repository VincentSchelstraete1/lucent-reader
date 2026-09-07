import json

import pytest

from app.retrieval_eval.dataset import load_retrieval_dataset
from app.retrieval_eval.evaluation import RetrievalResult, compare_failures, evaluate_retrieval


def _manifest():
    return {"version": "rag-eval-v1", "examples": [
        {"id": "supported-one", "documentAlias": "pendulum", "corpusHash": "a" * 64,
         "queryFamilyId": "turning-point", "split": "development", "category": "factual",
         "query": "Where is speed zero?", "supported": True,
         "gold": [{"blockIds": ["b1"], "quote": "speed is zero", "page": 1}]},
        {"id": "supported-multi", "documentAlias": "pendulum", "corpusHash": "a" * 64,
         "queryFamilyId": "energy-cycle", "split": "development", "category": "multi-block",
         "query": "Compare the top and bottom.", "supported": True,
         "gold": [{"blockIds": ["b1", "b2"]}]},
        {"id": "unsupported", "documentAlias": "pendulum", "corpusHash": "a" * 64,
         "queryFamilyId": "air-resistance", "split": "holdout", "category": "unsupported",
         "query": "What is the drag coefficient?", "supported": False, "gold": []},
    ]}


def test_loader_validates_fixed_family_splits_and_gold(tmp_path):
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(_manifest()))
    examples = load_retrieval_dataset(path)
    assert [item.id for item in examples] == ["supported-one", "supported-multi", "unsupported"]
    leaked = _manifest()
    leaked["examples"][2]["queryFamilyId"] = "turning-point"
    path.write_text(json.dumps(leaked))
    with pytest.raises(ValueError, match="leaks across splits"):
        load_retrieval_dataset(path)


def test_metrics_separate_supported_retrieval_and_unsupported_abstention(tmp_path):
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(_manifest()))
    examples = load_retrieval_dataset(path)
    results = {
        "supported-one": RetrievalResult(("wrong", "b1"), True, 10),
        "supported-multi": RetrievalResult(("b1", "other", "b2"), True, 20),
        "unsupported": RetrievalResult(("nearby",), False, 30),
    }
    summary = evaluate_retrieval(examples, lambda example: results[example.id])
    assert summary.recall_at_1 == 0.25
    assert summary.recall_at_3 == 1.0
    assert summary.recall_at_5 == 1.0
    assert summary.mrr == 0.75
    assert summary.complete_evidence_at_5 == 1.0
    assert summary.false_support_rate == 0.0
    assert summary.correct_abstention_rate == 1.0
    assert summary.p50_latency_ms == 20
    assert summary.p95_latency_ms == 30


def test_failure_comparison_reports_fixed_and_regressed(tmp_path):
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(_manifest()))
    examples = load_retrieval_dataset(path)
    baseline = evaluate_retrieval(examples, lambda example: RetrievalResult((), False))
    candidate = evaluate_retrieval(examples, lambda example: RetrievalResult(
        tuple(next(iter(example.gold)).block_ids) if example.supported else ("nearby",), True
    ))
    changes = compare_failures(baseline, candidate)
    assert "supported-one" in changes["fixed"]
    assert changes["regressions"] == ["unsupported"]
