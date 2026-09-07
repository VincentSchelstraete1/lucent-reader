#!/usr/bin/env python3
"""Seed licensed RAG evaluation fixtures into a local database."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.database import SessionLocal
from app.config import settings
from app.retrieval_eval.dataset import load_retrieval_dataset_bundle
from app.retrieval_eval.seeding import seed_retrieval_dataset
from app.services.embeddings import DeterministicEmbeddingProvider, VoyageEmbeddingProvider


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--provider", choices=("fake", "voyage"), required=True)
    parser.add_argument("--output-config", required=True)
    args = parser.parse_args()

    if settings.production:
        parser.error("Evaluation fixtures cannot be seeded into a production environment")
    dataset = load_retrieval_dataset_bundle(args.dataset)
    provider = DeterministicEmbeddingProvider() if args.provider == "fake" else VoyageEmbeddingProvider()
    with SessionLocal.begin() as db:
        config = seed_retrieval_dataset(db, dataset=dataset, provider=provider)
    destination = Path(args.output_config)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(config, indent=2) + "\n")
    print(json.dumps({
        "datasetVersion": dataset.version,
        "provider": config["provider"],
        "documents": {alias: item["documentId"] for alias, item in config["documents"].items()},
        "config": str(destination),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
