from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Literal


Split = Literal["development", "holdout"]


@dataclass(frozen=True)
class GoldEvidenceSet:
    block_ids: frozenset[str]
    quote: str | None = None
    page: int | None = None


@dataclass(frozen=True)
class RetrievalEvalExample:
    id: str
    document_alias: str
    document_id: int | None
    corpus_hash: str
    query_family_id: str
    split: Split
    category: str
    query: str
    supported: bool
    gold: tuple[GoldEvidenceSet, ...]


def load_retrieval_dataset(path: str | Path) -> list[RetrievalEvalExample]:
    payload = json.loads(Path(path).read_text())
    if not isinstance(payload, dict) or not isinstance(payload.get("examples"), list):
        raise ValueError("Retrieval dataset must contain an examples array")
    examples: list[RetrievalEvalExample] = []
    seen_ids: set[str] = set()
    family_splits: dict[str, str] = {}
    for raw in payload["examples"]:
        example_id = str(raw.get("id") or "")
        if not example_id or example_id in seen_ids:
            raise ValueError("Retrieval example IDs must be present and unique")
        seen_ids.add(example_id)
        split = str(raw.get("split") or "")
        if split not in {"development", "holdout"}:
            raise ValueError(f"Invalid split for {example_id}")
        family = str(raw.get("queryFamilyId") or "")
        if not family:
            raise ValueError(f"Missing query family for {example_id}")
        if family in family_splits and family_splits[family] != split:
            raise ValueError(f"Query family {family} leaks across splits")
        family_splits[family] = split
        corpus_hash = str(raw.get("corpusHash") or "")
        if len(corpus_hash) != 64:
            raise ValueError(f"Invalid corpus hash for {example_id}")
        supported = bool(raw.get("supported"))
        gold = tuple(
            GoldEvidenceSet(
                block_ids=frozenset(str(item) for item in entry.get("blockIds", [])),
                quote=entry.get("quote"),
                page=entry.get("page"),
            )
            for entry in raw.get("gold", [])
        )
        if supported and (not gold or any(not item.block_ids for item in gold)):
            raise ValueError(f"Supported example {example_id} needs non-empty gold evidence")
        if not supported and gold:
            raise ValueError(f"Unsupported example {example_id} cannot have gold evidence")
        query = " ".join(str(raw.get("query") or "").split())
        if not query:
            raise ValueError(f"Missing query for {example_id}")
        examples.append(RetrievalEvalExample(
            id=example_id, document_alias=str(raw.get("documentAlias") or ""),
            document_id=int(raw["documentId"]) if raw.get("documentId") is not None else None,
            corpus_hash=corpus_hash, query_family_id=family, split=split, category=str(raw.get("category") or "uncategorized"),
            query=query, supported=supported, gold=gold,
        ))
    return examples


def dataset_hash(examples: list[RetrievalEvalExample]) -> str:
    canonical = [{"id": item.id, "corpus": item.corpus_hash, "family": item.query_family_id,
                  "split": item.split, "query": item.query, "supported": item.supported,
                  "gold": [sorted(group.block_ids) for group in item.gold]} for item in examples]
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
