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
from app.retrieval_eval.dataset import dataset_hash, load_retrieval_dataset
from app.retrieval_eval.evaluation import RetrievalResult, compare_failures, evaluate_retrieval
from app.services.embeddings import DeterministicEmbeddingProvider, set_embedding_provider
from app.services.retrieval import RetrievalStatus, SourceQuery, retrieve_source


def _jsonable(value):
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "__dict__"):
        return _jsonable(asdict(value))
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--split", choices=("development", "holdout"), required=True)
    parser.add_argument("--provider", choices=("fake", "voyage"), required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--baseline")
    args = parser.parse_args()

    examples = [item for item in load_retrieval_dataset(args.dataset) if item.split == args.split]
    if args.provider == "fake":
        set_embedding_provider(DeterministicEmbeddingProvider())

    def strategy(example):
        if example.document_id is None:
            raise ValueError(f"Dataset example {example.id} needs documentId for a live database run")
        with SessionLocal() as db:
            row = db.execute(select(DocumentSourceIndex, Source.user_id).join(
                Document, Document.id == DocumentSourceIndex.document_id
            ).join(Source, Source.id == Document.source_id).where(DocumentSourceIndex.document_id == example.document_id)).one()
            source_index, user_id = row
            if source_index.corpus_hash != example.corpus_hash:
                raise ValueError(f"Corpus hash mismatch for {example.id}")
            context = retrieve_source(db, user_id=user_id, document_id=example.document_id,
                expected_generation=source_index.generation_id, query=SourceQuery("evaluation", example.query), top_k=5)
            return RetrievalResult(tuple(block.block_ids[0] for block in context.blocks),
                context.status == RetrievalStatus.SUPPORTED, context.timings_ms.get("total", 0.0))

    try:
        summary = evaluate_retrieval(examples, strategy)
    finally:
        set_embedding_provider(None)
    try:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    except Exception:
        revision = "unknown"
    artifact = {"gitRevision": revision, "datasetHash": dataset_hash(examples), "provider": args.provider,
                "split": args.split, "summary": _jsonable(summary)}
    if args.baseline:
        baseline = json.loads(Path(args.baseline).read_text()).get("summary", {})
        artifact["baselineSummary"] = baseline
        # Row-level comparison is available only when the baseline retained rows.
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(artifact, indent=2))
    print(json.dumps({key: value for key, value in artifact.items() if key != "summary"} | {
        "metrics": {key: artifact["summary"][key] for key in ("recall_at_1", "recall_at_3", "recall_at_5", "mrr", "false_support_rate")}
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
