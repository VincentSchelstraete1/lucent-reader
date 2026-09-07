import json
from pathlib import Path

import pytest

from app.retrieval_eval.dataset import fixture_corpus_hash, load_retrieval_dataset
from app.retrieval_eval.evaluation import RetrievalResult, compare_failures, evaluate_retrieval


def _manifest(tmp_path):
    blocks = [
        {"blockId": "b1", "text": "At the turning point, pendulum speed is zero.", "source": {"page_start": 1}},
        {"blockId": "b2", "text": "At the bottom, kinetic energy is greatest.", "source": {"page_start": 1}},
    ]
    fixture = tmp_path / "pendulum.json"
    fixture.write_text(json.dumps({"blocks": blocks}))
    corpus_hash = fixture_corpus_hash(blocks)
    return {"version": "rag-v1-test", "documents": [{
        "alias": "pendulum", "sourceFixture": "pendulum.json", "corpusHash": corpus_hash,
        "domain": "physics", "sourceType": "pdf",
    }], "examples": [
        {"id": "supported-one", "documentAlias": "pendulum", "corpusHash": corpus_hash,
         "queryFamilyId": "turning-point", "split": "development", "category": "factual",
         "query": "Where is speed zero?", "supported": True,
         "gold": [{"blockIds": ["b1"], "quote": "speed is zero", "page": 1, "offsetStart": 31, "offsetEnd": 44}]},
        {"id": "supported-multi", "documentAlias": "pendulum", "corpusHash": corpus_hash,
         "queryFamilyId": "energy-cycle", "split": "development", "category": "multi-block",
         "query": "Compare the top and bottom.", "supported": True,
         "gold": [{"blockIds": ["b1", "b2"], "spans": [
             {"blockId": "b1", "quote": "speed is zero", "page": 1, "offsetStart": 31, "offsetEnd": 44},
             {"blockId": "b2", "quote": "kinetic energy is greatest", "page": 1,
              "offsetStart": 15, "offsetEnd": 41},
         ]}]},
        {"id": "unsupported", "documentAlias": "pendulum", "corpusHash": corpus_hash,
         "queryFamilyId": "air-resistance", "split": "holdout", "category": "unsupported",
         "query": "What is the drag coefficient?", "supported": False, "gold": []},
    ]}


def test_loader_validates_fixed_family_splits_and_gold(tmp_path):
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(_manifest(tmp_path)))
    examples = load_retrieval_dataset(path)
    assert [item.id for item in examples] == ["supported-one", "supported-multi", "unsupported"]
    leaked = _manifest(tmp_path)
    leaked["examples"][2]["queryFamilyId"] = "turning-point"
    path.write_text(json.dumps(leaked))
    with pytest.raises(ValueError, match="leaks across splits"):
        load_retrieval_dataset(path)


def test_loader_rejects_source_drift_and_incomplete_multiblock_spans(tmp_path):
    path = tmp_path / "dataset.json"
    manifest = _manifest(tmp_path)
    manifest["examples"][1]["gold"][0]["spans"].pop()
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="cover every required block"):
        load_retrieval_dataset(path)

    manifest = _manifest(tmp_path)
    path.write_text(json.dumps(manifest))
    fixture = tmp_path / "pendulum.json"
    fixture.write_text(fixture.read_text().replace("speed is zero", "speed becomes zero"))
    with pytest.raises(ValueError, match="Corpus hash mismatch"):
        load_retrieval_dataset(path)


def test_checked_in_stage_manifests_are_locked_and_cover_required_domains():
    fixture_root = Path(__file__).parent / "fixtures" / "rag_v1"
    stage1 = load_retrieval_dataset(fixture_root / "stage1.json")
    stage2 = load_retrieval_dataset(fixture_root / "stage2.json")

    assert len(stage1) == 24
    assert {item.domain for item in stage1} == {"physics", "humanities"}
    assert {item.source_type for item in stage1} == {"pdf", "docx"}
    assert len(stage2) == 50
    assert {item.domain for item in stage2} == {"physics", "humanities", "computer_architecture"}
    assert {item.source_type for item in stage2} == {"pdf", "docx", "pptx"}
    assert sum(item.split == "holdout" for item in stage2) == 12
    assert all(group.spans and {span.block_id for span in group.spans} == set(group.block_ids)
               for item in stage2 if item.supported for group in item.gold)


def test_metrics_separate_supported_retrieval_and_unsupported_abstention(tmp_path):
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(_manifest(tmp_path)))
    examples = load_retrieval_dataset(path)
    results = {
        "supported-one": RetrievalResult(("wrong", "b1"), True, 10, ("b1",), 2, 3),
        "supported-multi": RetrievalResult(("b1", "other", "b2"), True, 20, ("b2", "b1"), 4, 6),
        "unsupported": RetrievalResult(("nearby",), False, 30, ("nearby",), 6, 9),
    }
    summary = evaluate_retrieval(examples, lambda example: results[example.id])
    assert summary.recall_at_1 == 0.25
    assert summary.recall_at_3 == 1.0
    assert summary.recall_at_5 == 1.0
    assert summary.mrr == 0.75
    assert summary.complete_evidence_at_5 == 1.0
    assert summary.hit_at_1 == 0.5
    assert summary.raw_recall_at_1 == 0.75
    assert summary.raw_recall_at_3 == 1.0
    assert summary.false_support_rate == 0.0
    assert summary.correct_abstention_rate == 1.0
    assert summary.p50_latency_ms == 20
    assert summary.p95_latency_ms == 30
    assert summary.p50_embedding_latency_ms == 4
    assert summary.p95_search_latency_ms == 9
    assert summary.macro_by_document["pendulum"]["recallAt5"] == 1.0


def test_failure_comparison_reports_fixed_and_regressed(tmp_path):
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(_manifest(tmp_path)))
    examples = load_retrieval_dataset(path)
    baseline = evaluate_retrieval(examples, lambda example: RetrievalResult((), False))
    candidate = evaluate_retrieval(examples, lambda example: RetrievalResult(
        tuple(next(iter(example.gold)).block_ids) if example.supported else ("nearby",), True
    ))
    changes = compare_failures(baseline, candidate)
    assert "supported-one" in changes["fixed"]
    assert changes["regressions"] == ["unsupported"]
