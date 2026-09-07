#!/usr/bin/env python3
"""Evaluate the real persisted retriever. Network use is explicit via --provider voyage."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import subprocess

from sqlalchemy import select

from app.database import SessionLocal
from app.models.document import Document
from app.models.learning_block import DocumentSourceIndex
from app.models.source import Source
from app.retrieval_eval.dataset import dataset_hash, load_retrieval_dataset_bundle
from app.retrieval_eval.evaluation import RetrievalResult, evaluate_retrieval
from app.retrieval_eval.seeding import config_hash
from app.retrieval_eval.support import AnthropicSupportDecisionProvider, DeterministicPresenceSupportProvider, SupportDecision
from app.services.embeddings import DeterministicEmbeddingProvider, VoyageEmbeddingProvider, set_embedding_provider
from app.services.retrieval import (
    DEFAULT_MIN_SIMILARITY,
    QUERY_VERSION,
    RETRIEVAL_POLICY_VERSION,
    RETRIEVAL_VERSION,
    RetrievalStatus,
    SourceQuery,
    retrieve_source,
)


def _jsonable(value):
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "__dict__"):
        return _jsonable(asdict(value))
    return value


def _load_config(path: str, *, dataset_hash_value: str, provider) -> dict:
    config = json.loads(Path(path).read_text())
    if config.get("version") != "rag-eval-config-v1":
        raise ValueError("Evaluation config has an unsupported version")
    if config.get("configHash") != config_hash(config):
        raise ValueError("Evaluation config hash does not match its contents")
    if config.get("datasetHash") != dataset_hash_value:
        raise ValueError("Evaluation config was seeded for a different dataset")
    expected = config.get("provider") or {}
    actual = provider.metadata
    if (expected.get("name"), expected.get("model"), expected.get("dimensions")) != (
        actual.provider, actual.model, actual.dimensions
    ):
        raise ValueError("Evaluation config provider does not match the selected provider")
    return config


def _row_payload(row) -> dict:
    selected_ids = list(row.result.ranked_block_ids)
    gold_sets = [sorted(group.block_ids) for group in row.example.gold]
    missed = [sorted(set(group) - set(selected_ids)) for group in gold_sets]
    return {
        "id": row.example.id,
        "documentAlias": row.example.document_alias,
        "domain": row.example.domain,
        "sourceType": row.example.source_type,
        "queryFamilyId": row.example.query_family_id,
        "category": row.example.category,
        "query": row.example.query,
        "supported": row.example.supported,
        "goldEvidenceSets": gold_sets,
        "rankedBlockIds": selected_ids,
        "rawRankedBlockIds": list(row.result.raw_ranked_block_ids or row.result.ranked_block_ids),
        "selectedBlocks": _jsonable(row.result.selected_blocks),
        "omittedBlockIds": list(row.result.omitted_block_ids),
        "missedGoldByEvidenceSet": missed,
        "answerSupported": row.result.answer_supported,
        "status": row.result.status,
        "failureCode": row.result.failure_code,
        "supportDecision": {
            "provider": row.result.support_provider,
            "answerSupported": row.result.answer_supported,
            "sourceBlockIds": list(row.result.support_block_ids),
            "reasonCode": row.result.support_reason,
        },
        "metrics": {
            "recallAt1": row.recall_at_1,
            "recallAt3": row.recall_at_3,
            "recallAt5": row.recall_at_5,
            "reciprocalRank": row.reciprocal_rank,
            "completeEvidenceAt5": row.complete_at_5,
        },
        "timingsMs": {
            "queryEmbedding": row.result.embedding_latency_ms,
            "search": row.result.search_latency_ms,
            "total": row.result.latency_ms,
        },
    }


def _markdown_summary(artifact: dict) -> str:
    summary = artifact["summary"]
    comparison = artifact.get("comparison") or {"fixed": [], "regressions": []}
    note = "Offline fake vectors; these numbers do not measure semantic quality." if not artifact["metadata"]["semanticQuality"] else "Live semantic embedding run."
    return "\n".join([
        f"# RAG retrieval evaluation — {artifact['metadata']['split']}",
        "",
        note,
        "",
        f"- Dataset: `{artifact['metadata']['datasetVersion']}` (`{artifact['metadata']['datasetHash']}`)",
        f"- Provider/model: `{artifact['metadata']['provider']}` / `{artifact['metadata']['model']}`",
        f"- Supported/unsupported: {summary['supported']} / {summary['unsupported']}",
        f"- Recall@1/@3/@5: {summary['recall_at_1']:.3f} / {summary['recall_at_3']:.3f} / {summary['recall_at_5']:.3f}",
        f"- Raw Recall@1/@3/@5: {summary['raw_recall_at_1']:.3f} / {summary['raw_recall_at_3']:.3f} / {summary['raw_recall_at_5']:.3f}",
        f"- MRR / complete evidence@5: {summary['mrr']:.3f} / {summary['complete_evidence_at_5']:.3f}",
        f"- False support / correct abstention: {summary['false_support_rate']:.3f} / {summary['correct_abstention_rate']:.3f}",
        f"- Total latency p50/p95 ms: {summary['p50_latency_ms']:.2f} / {summary['p95_latency_ms']:.2f}",
        f"- Fixed IDs: {', '.join(comparison['fixed']) or 'none'}",
        f"- Regressed IDs: {', '.join(comparison['regressions']) or 'none'}",
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--split", choices=("development", "holdout"), required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--provider", choices=("fake", "voyage"), required=True)
    parser.add_argument("--support-provider", choices=("fake", "anthropic"), required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--baseline")
    args = parser.parse_args()

    dataset = load_retrieval_dataset_bundle(args.dataset)
    full_dataset_hash = dataset_hash(list(dataset.examples))
    examples = [item for item in dataset.examples if item.split == args.split]
    provider = DeterministicEmbeddingProvider() if args.provider == "fake" else VoyageEmbeddingProvider()
    support_provider = (
        DeterministicPresenceSupportProvider()
        if args.support_provider == "fake"
        else AnthropicSupportDecisionProvider()
    )
    config = _load_config(args.config, dataset_hash_value=full_dataset_hash, provider=provider)
    document_config = config.get("documents") or {}
    top_k = int((config.get("retrieval") or {}).get("topK", 5))
    min_similarity = float((config.get("retrieval") or {}).get("minSimilarity", DEFAULT_MIN_SIMILARITY))
    if not 1 <= top_k <= 8:
        raise ValueError("Evaluation topK must be between 1 and 8")
    if not -1.0 <= min_similarity <= 1.0:
        raise ValueError("Evaluation minSimilarity must be between -1 and 1")
    set_embedding_provider(provider)

    with SessionLocal() as db:
        def strategy(example):
            mapped = document_config.get(example.document_alias)
            if not isinstance(mapped, dict) or mapped.get("documentId") is None:
                raise ValueError(f"Evaluation config has no document mapping for {example.document_alias}")
            document_id = int(mapped["documentId"])
            row = db.execute(select(DocumentSourceIndex, Source.user_id).join(
                Document, Document.id == DocumentSourceIndex.document_id
            ).join(Source, Source.id == Document.source_id).where(DocumentSourceIndex.document_id == document_id)).one()
            source_index, user_id = row
            if source_index.corpus_hash != example.corpus_hash or str(source_index.generation_id) != mapped.get("generationId"):
                raise ValueError(f"Corpus hash mismatch for {example.id}")
            context = retrieve_source(db, user_id=user_id, document_id=document_id,
                expected_generation=source_index.generation_id,
                query=SourceQuery("evaluation", example.query), top_k=top_k,
                min_similarity=min_similarity)
            selected_blocks = tuple({
                "blockIds": block.block_ids,
                "rank": block.rank,
                "score": block.score,
                "selection": block.selection,
                "source": block.source,
                "excerpt": block.text,
            } for block in context.blocks)
            support = (
                SupportDecision(False, (), "below_similarity_cutoff")
                if context.status == RetrievalStatus.WEAK
                else support_provider.decide(query=example.query, selected_blocks=selected_blocks)
            )
            return RetrievalResult(
                ranked_block_ids=tuple(block.block_ids[0] for block in context.blocks),
                answer_supported=support.answer_supported,
                latency_ms=context.timings_ms.get("total", 0.0),
                raw_ranked_block_ids=tuple(context.raw_ranked_block_ids),
                embedding_latency_ms=context.timings_ms.get("query_embedding", 0.0),
                search_latency_ms=context.timings_ms.get("search", 0.0),
                status=context.status.value,
                selected_blocks=selected_blocks,
                omitted_block_ids=tuple(context.omitted_block_ids),
                failure_code=context.failure_code,
                support_block_ids=support.source_block_ids,
                support_reason=support.reason_code,
                support_provider=support_provider.name,
            )

        try:
            summary = evaluate_retrieval(examples, strategy)
        finally:
            set_embedding_provider(None)
    try:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    except Exception:
        revision = "unknown"
    summary_payload = _jsonable(asdict(summary))
    summary_payload.pop("rows", None)
    summary_payload.pop("failures", None)
    rows = [_row_payload(row) for row in summary.rows]
    failure_ids = [row.example.id for row in summary.failures]
    artifact = {
        "version": "rag-eval-run-v1",
        "metadata": {
            "gitRevision": revision,
            "datasetVersion": dataset.version,
            "datasetHash": full_dataset_hash,
            "corpusHashes": {alias: fixture.corpus_hash for alias, fixture in sorted(dataset.fixtures.items())},
            "configHash": config["configHash"],
            "provider": provider.metadata.provider,
            "model": provider.metadata.model,
            "dimensions": provider.metadata.dimensions,
            "supportProvider": support_provider.name,
            "supportModel": support_provider.model,
            "supportPolicyVersion": getattr(support_provider, "policy_version", "presence-v1"),
            "embeddingInputVersion": "learning-block-input-v1",
            "queryVersion": QUERY_VERSION,
            "retrievalVersion": RETRIEVAL_VERSION,
            "retrievalPolicyVersion": RETRIEVAL_POLICY_VERSION,
            "minSimilarity": min_similarity,
            "split": args.split,
            "corpusSizeBlocks": sum(int(item["blockCount"]) for item in document_config.values()),
            "latencyMethodology": (config.get("retrieval") or {}).get("latencyMethodology"),
            "semanticQuality": provider.metadata.provider != "fake" and support_provider.name != "fake",
        },
        "config": config,
        "summary": summary_payload,
        "failureIds": failure_ids,
        "rows": rows,
    }
    if args.baseline:
        baseline = json.loads(Path(args.baseline).read_text())
        baseline_meta = baseline.get("metadata") or {}
        if baseline_meta.get("datasetHash") != full_dataset_hash or baseline_meta.get("split") != args.split:
            raise ValueError("Baseline dataset and split must match the candidate run")
        before = set(baseline.get("failureIds") or [])
        after = set(failure_ids)
        artifact["comparison"] = {"fixed": sorted(before - after), "regressions": sorted(after - before)}
    else:
        artifact["comparison"] = {"fixed": [], "regressions": []}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(artifact, indent=2) + "\n")
    markdown_path = Path(args.output).with_suffix(".md")
    markdown_path.write_text(_markdown_summary(artifact))
    print(json.dumps({"artifact": args.output, "summary": str(markdown_path),
        "metadata": artifact["metadata"], "metrics": artifact["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
