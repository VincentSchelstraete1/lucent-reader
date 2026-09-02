"""Reads the single shared dataset at web/src/learning/routing/evaluation/
routerDataset.json rather than maintaining an independent Python copy - see
that file's TS sibling for why. split_router_dataset() below is a byte-exact
port of routerDataset.ts's splitRouterDataset (same FNV-1a stable_hash), so
Python and TypeScript produce the identical dev/holdout membership.
"""

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.routing.representation_types import RepresentationType


DATASET_SPLIT_SEED = "lucent-router-evaluation-v1"
DatasetPartition = Literal["development", "holdout"]

_DATASET_PATH = Path(__file__).resolve().parents[3] / "web" / "src" / "learning" / "routing" / "evaluation" / "routerDataset.json"


@dataclass(frozen=True)
class RouterExample:
    id: str
    expected: RepresentationType
    text: str
    subject: str
    style: str
    ambiguous: bool = False
    acceptable_types: list[RepresentationType] | None = None
    ambiguity_note: str | None = None


def _load_raw() -> list[dict]:
    return json.loads(_DATASET_PATH.read_text())


def load_router_dataset() -> list[RouterExample]:
    return [
        RouterExample(
            id=item["id"],
            expected=item["expected"],
            text=item["text"],
            subject=item["subject"],
            style=item["style"],
            ambiguous=item.get("ambiguous", False),
            acceptable_types=item.get("acceptableTypes"),
            ambiguity_note=item.get("ambiguityNote"),
        )
        for item in _load_raw()
    ]


def stable_hash(value: str) -> int:
    """FNV-1a 32-bit, matching routerDataset.ts's stableHash (Math.imul +
    >>> 0) exactly: masking to 32 bits after each multiplication reproduces
    JS's 32-bit wraparound."""

    hash_value = 2166136261
    for char in value:
        hash_value ^= ord(char)
        hash_value = (hash_value * 16777619) & 0xFFFFFFFF
    return hash_value


def split_router_dataset(examples: list[RouterExample] | None = None) -> dict[DatasetPartition, list[RouterExample]]:
    examples = examples if examples is not None else load_router_dataset()
    groups: dict[str, list[RouterExample]] = {}
    for example in examples:
        key = f"{'ambiguous' if example.ambiguous else 'strict'}:{example.expected}"
        groups.setdefault(key, []).append(example)

    development: list[RouterExample] = []
    holdout: list[RouterExample] = []
    for group in groups.values():
        ordered = sorted(group, key=lambda example: (stable_hash(f"{DATASET_SPLIT_SEED}:{example.id}"), example.id))
        # Python's round() is round-half-to-even; JS's Math.round is
        # round-half-up. math.floor(x + 0.5) matches Math.round for the
        # non-negative values here.
        holdout_count = max(1, math.floor(len(ordered) * 0.25 + 0.5))
        holdout.extend(ordered[:holdout_count])
        development.extend(ordered[holdout_count:])

    return {
        "development": sorted(development, key=lambda example: example.id),
        "holdout": sorted(holdout, key=lambda example: example.id),
    }
