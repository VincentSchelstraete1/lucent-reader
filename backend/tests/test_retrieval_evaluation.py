import json
from pathlib import Path
import sys

import pytest

from app.retrieval_eval.dataset import fixture_corpus_hash, load_retrieval_dataset, load_retrieval_dataset_bundle
from app.retrieval_eval.evaluation import RetrievalResult, compare_failures, evaluate_retrieval
from app.retrieval_eval.seeding import seed_retrieval_dataset
from app.retrieval_eval.support import AnthropicSupportDecisionProvider
from app.services.embeddings import DeterministicEmbeddingProvider
from tests.conftest import TestSessionLocal


def _manifest(tmp_path):
    blocks = [
        {"blockId": "b1", "text": "At the turning point, pendulum speed is zero.", "source": {"page_start": 1}},
        {"blockId": "b2", "text": "At the bottom, kinetic energy is greatest.", "source": {"page_start": 1}},
    ]
    fixture = tmp_path / "pendulum.json"
    fixture.write_text(json.dumps({
        "title": "Pendulum test fixture", "license": "CC0-1.0", "blocks": blocks,
    }))
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
    assert summary.supported_false_refusal_rate == 0.0
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


def test_supported_false_refusal_is_retained_as_failure(tmp_path):
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(_manifest(tmp_path)))
    examples = load_retrieval_dataset(path)
    summary = evaluate_retrieval(examples, lambda example: RetrievalResult(
        tuple(next(iter(example.gold)).block_ids) if example.supported else ("nearby",),
        False,
    ))
    assert {row.example.id for row in summary.failures} == {"supported-one", "supported-multi"}


def test_anthropic_support_decision_rejects_unavailable_source_ids(monkeypatch):
    from app.services import anthropic_service

    monkeypatch.setattr(anthropic_service, "_run_structured_tool", lambda *args, **kwargs: {
        "answerSupported": True,
        "sourceBlockIds": ["invented-block"],
        "reasonCode": "direct_support",
    })
    decision = AnthropicSupportDecisionProvider().decide(
        query="What happens at the turning point?",
        selected_blocks=[{"blockIds": ["pendulum-turning"], "excerpt": "Speed is zero."}],
    )
    assert decision.answer_supported is False
    assert decision.source_block_ids == ()
    assert decision.reason_code == "invalid_source_reference"


def test_anthropic_support_decision_clears_refusal_citations(monkeypatch):
    from app.services import anthropic_service

    def decide(prompt, *args, **kwargs):
        return {
            "answerSupported": False,
            "sourceBlockIds": ["cache-direct"],
            "reasonCode": "missing_fact",
        }

    monkeypatch.setattr(anthropic_service, "_run_structured_tool", decide)
    decision = AnthropicSupportDecisionProvider().decide(
        query="How many possible cache lines can hold a block?",
        selected_blocks=[{
            "blockIds": ["cache-direct"],
            "excerpt": "Each memory block can occupy exactly one cache line.",
        }],
    )

    assert decision.answer_supported is False
    assert decision.source_block_ids == ()


def test_local_seed_and_cli_emit_reproducible_complete_artifact(tmp_path, monkeypatch):
    from scripts import evaluate_retrieval as cli

    dataset_path = Path(__file__).parent / "fixtures" / "rag_v1" / "stage1.json"
    dataset = load_retrieval_dataset_bundle(dataset_path)
    provider = DeterministicEmbeddingProvider()
    with TestSessionLocal.begin() as db:
        first = seed_retrieval_dataset(db, dataset=dataset, provider=provider)
    with TestSessionLocal.begin() as db:
        second = seed_retrieval_dataset(db, dataset=dataset, provider=provider)
    assert first == second

    config_path = tmp_path / "config.json"
    output_path = tmp_path / "development.json"
    config_path.write_text(json.dumps(first))
    monkeypatch.setattr(sys, "argv", [
        "evaluate_retrieval.py",
        "--dataset", str(dataset_path),
        "--split", "development",
        "--config", str(config_path),
        "--provider", "fake",
        "--support-provider", "fake",
        "--output", str(output_path),
    ])
    assert cli.main() == 0

    artifact = json.loads(output_path.read_text())
    assert artifact["version"] == "rag-eval-run-v1"
    assert artifact["metadata"]["semanticQuality"] is False
    assert artifact["metadata"]["supportProvider"] == "fake"
    assert artifact["metadata"]["corpusSizeBlocks"] == 16
    assert artifact["summary"]["total"] == 20
    assert len(artifact["rows"]) == 20
    assert all(row["rawRankedBlockIds"] and row["selectedBlocks"] for row in artifact["rows"])
    assert all("excerpt" in block for row in artifact["rows"] for block in row["selectedBlocks"])
    assert all(row["supportDecision"]["reasonCode"] == "fake_presence" for row in artifact["rows"])
    assert "do not measure semantic quality" in output_path.with_suffix(".md").read_text()

    candidate_path = tmp_path / "candidate.json"
    monkeypatch.setattr(sys, "argv", [
        "evaluate_retrieval.py",
        "--dataset", str(dataset_path),
        "--split", "development",
        "--config", str(config_path),
        "--provider", "fake",
        "--support-provider", "fake",
        "--output", str(candidate_path),
        "--baseline", str(output_path),
    ])
    assert cli.main() == 0
    assert json.loads(candidate_path.read_text())["comparison"] == {"fixed": [], "regressions": []}

    tampered = {**first, "retrieval": {**first["retrieval"], "topK": 4}}
    config_path.write_text(json.dumps(tampered))
    with pytest.raises(ValueError, match="config hash"):
        cli._load_config(str(config_path), dataset_hash_value=first["datasetHash"], provider=provider)
