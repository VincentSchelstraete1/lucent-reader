#!/usr/bin/env python3
"""Run the real (live Anthropic API) comparison of deterministic-only,
classifier-only, and hybrid routing on the router dataset's holdout split.
Not part of the automated test suite - costs real API calls. Run from
`backend/` with the venv active and ANTHROPIC_API_KEY set:

    PYTHONPATH=. python scripts/evaluate_hybrid_router.py
"""

import json
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.routing.classifier import AnthropicClassifierAdapter
from app.routing.dataset import split_router_dataset
from app.routing.hybrid import should_fallback
from app.routing.router import route_representation


def main() -> None:
    holdout = [example for example in split_router_dataset()["holdout"] if not example.ambiguous]
    classifier = AnthropicClassifierAdapter()

    rows = []
    total_latency = 0.0
    for example in holdout:
        deterministic_route = route_representation(example.text)
        fallback_triggered = should_fallback(deterministic_route)

        # Call the classifier on every example (not just fallback-triggered
        # ones) so classifier-only accuracy can be measured too.
        start = time.time()
        classified_type = classifier.classify(example.text)
        latency = time.time() - start
        total_latency += latency

        hybrid_type = classified_type if (fallback_triggered and classified_type) else deterministic_route.type
        rows.append({
            "id": example.id, "expected": example.expected,
            "deterministic": deterministic_route.type, "classifier": classified_type,
            "fallback_triggered": fallback_triggered, "hybrid": hybrid_type, "latency": round(latency, 3),
        })

    def accuracy(key: str) -> float:
        return round(sum(row["expected"] == row[key] for row in rows) / len(rows), 4)

    fallback_rows = [row for row in rows if row["fallback_triggered"]]
    non_fallback_rows = [row for row in rows if not row["fallback_triggered"]]

    print(json.dumps({
        "holdout_size": len(rows),
        "deterministic_only_accuracy": accuracy("deterministic"),
        "classifier_only_accuracy": accuracy("classifier"),
        "hybrid_accuracy": accuracy("hybrid"),
        "deterministic_coverage": round(len(non_fallback_rows) / len(rows), 4),
        "deterministic_subset_accuracy": (
            round(sum(row["expected"] == row["deterministic"] for row in non_fallback_rows) / len(non_fallback_rows), 4)
            if non_fallback_rows else None
        ),
        "fallback_rate": round(len(fallback_rows) / len(rows), 4),
        "fallback_accuracy": (
            round(sum(row["expected"] == row["classifier"] for row in fallback_rows) / len(fallback_rows), 4)
            if fallback_rows else None
        ),
        "regressions": [row["id"] for row in rows if row["deterministic"] == row["expected"] and row["hybrid"] != row["expected"]],
        "total_classifier_calls": len(rows),
        "total_latency_seconds": round(total_latency, 2),
        "average_latency_seconds": round(total_latency / len(rows), 3) if rows else None,
        "rows": rows,
    }, indent=2))


if __name__ == "__main__":
    main()
