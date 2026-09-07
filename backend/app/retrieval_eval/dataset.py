from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Literal


Split = Literal["development", "holdout"]


@dataclass(frozen=True)
class RetrievalFixture:
    alias: str
    path: Path
    corpus_hash: str
    domain: str
    source_type: str
    title: str
    license: str
    blocks: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class GoldSpan:
    block_id: str
    quote: str
    offset_start: int
    offset_end: int
    page: int | None = None


@dataclass(frozen=True)
class GoldEvidenceSet:
    block_ids: frozenset[str]
    spans: tuple[GoldSpan, ...]


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
    domain: str = "unknown"
    source_type: str = "unknown"
    learner_context: str | None = None
    objective_context: str | None = None


@dataclass(frozen=True)
class RetrievalDataset:
    version: str
    path: Path
    fixtures: dict[str, RetrievalFixture]
    examples: tuple[RetrievalEvalExample, ...]


def fixture_corpus_hash(blocks: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> str:
    canonical = json.dumps(list(blocks), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load_fixtures(manifest_path: Path, payload: dict[str, Any]) -> dict[str, RetrievalFixture]:
    raw_documents = payload.get("documents")
    if not isinstance(raw_documents, list) or not raw_documents:
        raise ValueError("Retrieval dataset must declare source documents")
    fixtures: dict[str, RetrievalFixture] = {}
    for raw in raw_documents:
        alias = str(raw.get("alias") or "").strip()
        relative = str(raw.get("sourceFixture") or "").strip()
        domain = str(raw.get("domain") or "").strip()
        source_type = str(raw.get("sourceType") or "").strip()
        if not alias or alias in fixtures or not relative or not domain or source_type not in {"pdf", "docx", "pptx"}:
            raise ValueError("Each retrieval source needs a unique alias, fixture, domain, and supported source type")
        fixture_path = (manifest_path.parent / relative).resolve()
        try:
            fixture_payload = json.loads(fixture_path.read_text())
        except (OSError, ValueError) as exc:
            raise ValueError(f"Source fixture for {alias} is unavailable") from exc
        blocks = fixture_payload.get("blocks") if isinstance(fixture_payload, dict) else None
        if not isinstance(blocks, list) or not blocks:
            raise ValueError(f"Source fixture for {alias} has no blocks")
        block_ids = [str(block.get("blockId") or "") for block in blocks if isinstance(block, dict)]
        if len(block_ids) != len(blocks) or any(not value for value in block_ids) or len(set(block_ids)) != len(block_ids):
            raise ValueError(f"Source fixture for {alias} has invalid block IDs")
        actual_hash = fixture_corpus_hash(blocks)
        declared_hash = str(raw.get("corpusHash") or "")
        if declared_hash != actual_hash:
            raise ValueError(f"Corpus hash mismatch for source fixture {alias}")
        title = str(fixture_payload.get("title") or "").strip()
        license_name = str(fixture_payload.get("license") or "").strip()
        if not title or not license_name:
            raise ValueError(f"Source fixture for {alias} needs title and license metadata")
        fixtures[alias] = RetrievalFixture(alias=alias, path=fixture_path, corpus_hash=actual_hash,
            domain=domain, source_type=source_type, title=title, license=license_name, blocks=tuple(blocks))
    return fixtures


def _validate_gold(example_id: str, raw_gold: list[Any], fixture: RetrievalFixture) -> tuple[GoldEvidenceSet, ...]:
    by_id = {str(block["blockId"]): block for block in fixture.blocks}
    gold: list[GoldEvidenceSet] = []
    for entry in raw_gold:
        ids = frozenset(str(item) for item in entry.get("blockIds", []))
        if not ids or not ids <= set(by_id):
            raise ValueError(f"Gold evidence for {example_id} references an unknown block")
        raw_spans = entry.get("spans")
        if raw_spans is None and len(ids) == 1:
            raw_spans = [{**entry, "blockId": next(iter(ids))}]
        if not isinstance(raw_spans, list) or not raw_spans:
            raise ValueError(f"Gold evidence for {example_id} needs a verified span for every required block")
        spans: list[GoldSpan] = []
        for raw_span in raw_spans:
            block_id = str(raw_span.get("blockId") or "")
            quote = str(raw_span.get("quote") or "")
            offset_start = raw_span.get("offsetStart")
            offset_end = raw_span.get("offsetEnd")
            if block_id not in ids or not quote:
                raise ValueError(f"Gold span for {example_id} must reference one required block")
            if not isinstance(offset_start, int) or not isinstance(offset_end, int) or offset_start < 0 or offset_end <= offset_start:
                raise ValueError(f"Gold offsets for {example_id} are invalid")
            text = str(by_id[block_id].get("text") or "")
            if text[offset_start:offset_end] != quote:
                raise ValueError(f"Gold span for {example_id} does not match its quote")
            page = raw_span.get("page")
            if page is not None and int((by_id[block_id].get("source") or {}).get("page_start") or -1) != int(page):
                raise ValueError(f"Gold page for {example_id} does not resolve to its block")
            spans.append(GoldSpan(block_id=block_id, quote=quote, offset_start=offset_start,
                offset_end=offset_end, page=int(page) if page is not None else None))
        if {span.block_id for span in spans} != set(ids):
            raise ValueError(f"Gold evidence for {example_id} must cover every required block")
        gold.append(GoldEvidenceSet(block_ids=ids, spans=tuple(spans)))
    return tuple(gold)


def _load_manifest(path: Path, seen: set[Path] | None = None) -> dict[str, Any]:
    seen = set(seen or ())
    if path in seen:
        raise ValueError("Retrieval dataset manifests cannot include a cycle")
    seen.add(path)
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("Retrieval dataset must be a JSON object")
    parent = payload.get("extends")
    if not parent:
        return payload
    parent_path = (path.parent / str(parent)).resolve()
    base = _load_manifest(parent_path, seen)
    return {
        **base,
        **{key: value for key, value in payload.items() if key not in {"documents", "examples", "extends"}},
        "documents": [*(base.get("documents") or []), *(payload.get("documents") or [])],
        "examples": [*(base.get("examples") or []), *(payload.get("examples") or [])],
    }


def load_retrieval_dataset_bundle(path: str | Path) -> RetrievalDataset:
    manifest_path = Path(path).resolve()
    payload = _load_manifest(manifest_path)
    if not isinstance(payload, dict) or not isinstance(payload.get("examples"), list):
        raise ValueError("Retrieval dataset must contain an examples array")
    if not str(payload.get("version") or "").startswith("rag-v1-"):
        raise ValueError("Retrieval dataset needs a versioned RAG V1 manifest")
    fixtures = _load_fixtures(manifest_path, payload)
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
        alias = str(raw.get("documentAlias") or "")
        fixture = fixtures.get(alias)
        if fixture is None:
            raise ValueError(f"Unknown source fixture for {example_id}")
        corpus_hash = str(raw.get("corpusHash") or fixture.corpus_hash)
        if corpus_hash != fixture.corpus_hash:
            raise ValueError(f"Invalid corpus hash for {example_id}")
        supported = bool(raw.get("supported"))
        raw_gold = raw.get("gold", [])
        if not isinstance(raw_gold, list):
            raise ValueError(f"Invalid gold evidence for {example_id}")
        gold = _validate_gold(example_id, raw_gold, fixture) if raw_gold else ()
        if supported and not gold:
            raise ValueError(f"Supported example {example_id} needs non-empty gold evidence")
        if not supported and gold:
            raise ValueError(f"Unsupported example {example_id} cannot have gold evidence")
        query = " ".join(str(raw.get("query") or "").split())
        if not query:
            raise ValueError(f"Missing query for {example_id}")
        examples.append(RetrievalEvalExample(
            id=example_id, document_alias=alias,
            document_id=int(raw["documentId"]) if raw.get("documentId") is not None else None,
            corpus_hash=corpus_hash, query_family_id=family, split=split,
            category=str(raw.get("category") or "uncategorized"), query=query,
            supported=supported, gold=gold, domain=fixture.domain, source_type=fixture.source_type,
            learner_context=str(raw.get("learnerContext")) if raw.get("learnerContext") else None,
            objective_context=str(raw.get("objectiveContext")) if raw.get("objectiveContext") else None,
        ))
    return RetrievalDataset(
        version=str(payload["version"]), path=manifest_path, fixtures=fixtures, examples=tuple(examples)
    )


def load_retrieval_dataset(path: str | Path) -> list[RetrievalEvalExample]:
    return list(load_retrieval_dataset_bundle(path).examples)


def dataset_hash(examples: list[RetrievalEvalExample]) -> str:
    canonical = [{"id": item.id, "document": item.document_alias, "corpus": item.corpus_hash,
                  "domain": item.domain, "sourceType": item.source_type, "family": item.query_family_id,
                  "split": item.split, "category": item.category, "query": item.query,
                  "learnerContext": item.learner_context, "objectiveContext": item.objective_context,
                  "supported": item.supported,
                  "gold": [{"blocks": sorted(group.block_ids), "spans": [
                      {"block": span.block_id, "quote": span.quote, "start": span.offset_start,
                       "end": span.offset_end, "page": span.page} for span in group.spans
                  ]} for group in item.gold]} for item in examples]
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
