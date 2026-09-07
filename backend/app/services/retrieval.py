"""Authoritative, document-scoped retrieval of persisted original source blocks."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import json
import os
import time
from typing import Any, Sequence
import uuid

from sqlalchemy import select

from app.models.document import Document
from app.models.learning_block import DocumentSourceIndex, PersistedLearningBlock
from app.models.source import Source
from app.services.embeddings import EmbeddingError, get_embedding_provider


class RetrievalStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    WEAK = "WEAK"
    NOT_INDEXED = "NOT_INDEXED"
    INDEXING = "INDEXING"
    FAILED = "FAILED"
    SOURCE_CHANGED = "SOURCE_CHANGED"


class SourceAccessDenied(LookupError):
    pass


class SourceContextUnavailable(RuntimeError):
    def __init__(self, status: RetrievalStatus) -> None:
        self.status = status
        super().__init__("Grounded source context is temporarily unavailable")


@dataclass(frozen=True)
class SourceQuery:
    purpose: str
    text: str
    objective_id: str | None = None


@dataclass(frozen=True)
class RetrievedSourceBlock:
    text: str
    block_ids: list[str]
    section_ids: list[str]
    source: dict[str, Any]
    ordinal: int
    rank: int
    score: float | None
    selection: str
    excerpt_start: int = 0
    excerpt_end: int = 0

    def observation_dict(self) -> dict[str, Any]:
        return {"text": self.text, "sectionIds": self.section_ids, "blockIds": self.block_ids}


@dataclass(frozen=True)
class RetrievedSourceContext:
    status: RetrievalStatus
    document_id: int
    generation_id: uuid.UUID | None
    query_fingerprint: str
    provider: str | None = None
    model: str | None = None
    dimensions: int | None = None
    blocks: list[RetrievedSourceBlock] = field(default_factory=list)
    coverage_incomplete: bool = False
    truncated: bool = False
    timings_ms: dict[str, float] = field(default_factory=dict)
    failure_code: str | None = None

    @property
    def text(self) -> str:
        return "\n\n".join(block.text for block in self.blocks)

    def observation_blocks(self) -> list[dict[str, Any]]:
        return [block.observation_dict() for block in self.blocks]

    def legacy_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "sourceSectionIds": list(dict.fromkeys(item for block in self.blocks for item in block.section_ids)),
            "sourceBlockIds": list(dict.fromkeys(item for block in self.blocks for item in block.block_ids)),
            "retrievalStatus": self.status.value,
            "sourceGeneration": str(self.generation_id) if self.generation_id else None,
        }


def _bounded(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def build_source_query(
    *, purpose: str, objective_title: str = "", objective_outcome: str = "", active_prompt: str = "",
    learner_text: str = "", evidence_target: str = "", misconception: str = "", objective_id: str | None = None,
) -> SourceQuery:
    concept = _bounded(f"{objective_title}. {objective_outcome}", 350)
    prompt = _bounded(active_prompt, 450)
    learner = _bounded(learner_text, 250)
    if learner.casefold() in {"i don't know", "i dont know", "not sure", "i'm not sure", "im not sure"}:
        learner = ""
    remaining = max(0, 1200 - len(concept) - len(prompt) - len(learner) - 4)
    evidence = _bounded(f"{evidence_target}. {misconception}", remaining)
    text = "\n".join(item for item in (concept, prompt, learner, evidence) if item).strip()
    if not text:
        raise ValueError("A source query requires bounded concept or learner context")
    return SourceQuery(purpose=purpose, text=text[:1200], objective_id=objective_id)


def exact_cosine(unit_query: Sequence[float], unit_document: Sequence[float]) -> float:
    if len(unit_query) != len(unit_document):
        raise ValueError("Embedding dimensions do not match")
    return float(sum(left * right for left, right in zip(unit_query, unit_document)))


def _empty_context(status: RetrievalStatus, *, document_id: int, generation_id: uuid.UUID | None,
                   fingerprint: str, index: DocumentSourceIndex | None = None,
                   failure_code: str | None = None) -> RetrievedSourceContext:
    return RetrievedSourceContext(status=status, document_id=document_id, generation_id=generation_id,
        query_fingerprint=fingerprint, provider=index.provider if index else None,
        model=index.model if index else None, dimensions=index.dimensions if index else None,
        failure_code=failure_code)


def retrieve_source(db, *, user_id: uuid.UUID, document_id: int, expected_generation: uuid.UUID | None,
                    query: SourceQuery, anchor_block_ids: Sequence[str] = (), top_k: int = 5) -> RetrievedSourceContext:
    started = time.perf_counter()
    fingerprint = hashlib.sha256(query.text.encode("utf-8")).hexdigest()[:16]
    owned = db.execute(select(Document.id).join(Source).where(Document.id == document_id, Source.user_id == user_id)).scalar_one_or_none()
    if owned is None:
        raise SourceAccessDenied("Source document was not found")
    source_index = db.get(DocumentSourceIndex, document_id)
    if source_index is None:
        return _empty_context(RetrievalStatus.NOT_INDEXED, document_id=document_id, generation_id=None, fingerprint=fingerprint)
    if expected_generation is not None and source_index.generation_id != expected_generation:
        return _empty_context(RetrievalStatus.SOURCE_CHANGED, document_id=document_id, generation_id=source_index.generation_id,
                              fingerprint=fingerprint, index=source_index)
    if source_index.status != "READY":
        status = RetrievalStatus.INDEXING if source_index.status in {"PENDING", "INDEXING"} else RetrievalStatus.FAILED
        return _empty_context(status, document_id=document_id, generation_id=source_index.generation_id,
                              fingerprint=fingerprint, index=source_index, failure_code=source_index.failure_code)

    rows = db.execute(select(PersistedLearningBlock).where(
        PersistedLearningBlock.document_id == document_id,
        PersistedLearningBlock.generation_id == source_index.generation_id,
    ).order_by(PersistedLearningBlock.ordinal, PersistedLearningBlock.block_id)).scalars().all()
    row_by_id = {row.block_id: row for row in rows}
    selected: list[tuple[PersistedLearningBlock, float | None, str]] = []
    seen: set[str] = set()
    missing_anchor = False
    for block_id in list(dict.fromkeys(str(item) for item in anchor_block_ids))[:3]:
        row = row_by_id.get(block_id)
        if row is None:
            missing_anchor = True
            continue
        selected.append((row, None, "anchor"))
        seen.add(row.block_id)

    embedding_started = time.perf_counter()
    try:
        provider = get_embedding_provider()
        if (provider.metadata.provider, provider.metadata.model, provider.metadata.dimensions) != (
            source_index.provider, source_index.model, source_index.dimensions
        ):
            return _empty_context(RetrievalStatus.FAILED, document_id=document_id,
                generation_id=source_index.generation_id, fingerprint=fingerprint, index=source_index,
                failure_code="embedding_configuration_mismatch")
        query_vector = provider.embed_query(query.text)
    except EmbeddingError:
        return _empty_context(RetrievalStatus.FAILED, document_id=document_id,
            generation_id=source_index.generation_id, fingerprint=fingerprint, index=source_index,
            failure_code="embedding_unavailable")
    embedding_ms = (time.perf_counter() - embedding_started) * 1000

    search_started = time.perf_counter()
    scored: list[tuple[float, PersistedLearningBlock]] = []
    for row in rows:
        if row.block_id in seen or not isinstance(row.embedding, list):
            continue
        try:
            scored.append((exact_cosine(query_vector, row.embedding), row))
        except (TypeError, ValueError):
            continue
    scored.sort(key=lambda item: (-item[0], item[1].ordinal, item[1].block_id))
    semantic_limit = max(0, min(int(top_k), 8) - len(selected))
    selected.extend((row, score, "semantic") for score, row in scored[:semantic_limit])
    search_ms = (time.perf_counter() - search_started) * 1000

    output: list[RetrievedSourceBlock] = []
    used = 0
    truncated = False
    for row, score, selection in selected[:8]:
        excerpt = row.text.strip()
        if len(excerpt) > 3000:
            excerpt = excerpt[:3000].rsplit(" ", 1)[0].strip()
            truncated = True
        remaining = 8000 - used
        if remaining <= 0:
            truncated = True
            break
        if len(excerpt) > remaining:
            excerpt = excerpt[:remaining].rsplit(" ", 1)[0].strip()
            truncated = True
        if not excerpt:
            continue
        output.append(RetrievedSourceBlock(text=excerpt, block_ids=[row.block_id],
            section_ids=list(row.section_ids or []), source=dict(row.source or {}), ordinal=row.ordinal,
            rank=len(output) + 1, score=score, selection=selection, excerpt_end=len(excerpt)))
        used += len(excerpt)

    threshold_text = os.getenv("RAG_MIN_SIMILARITY", "").strip()
    threshold = float(threshold_text) if threshold_text else None
    semantic_scores = [block.score for block in output if block.score is not None]
    status = RetrievalStatus.SUPPORTED if output else RetrievalStatus.WEAK
    if threshold is not None and semantic_scores and max(semantic_scores) < threshold and not any(block.selection == "anchor" for block in output):
        status = RetrievalStatus.WEAK
    return RetrievedSourceContext(status=status, document_id=document_id, generation_id=source_index.generation_id,
        query_fingerprint=fingerprint, provider=source_index.provider, model=source_index.model,
        dimensions=source_index.dimensions, blocks=output, coverage_incomplete=missing_anchor,
        truncated=truncated, timings_ms={"query_embedding": embedding_ms, "search": search_ms,
                                        "total": (time.perf_counter() - started) * 1000})


def serialize_source_context(context: RetrievedSourceContext, *, max_chars: int = 8000) -> str:
    payload = [{"blockIds": block.block_ids, "sectionIds": block.section_ids,
                "source": block.source, "text": block.text} for block in context.blocks]
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))[:max_chars]


def retrieve_note_context(note_payload: dict, query: str, limit: int = 3) -> dict:
    """Legacy generated-note lookup retained only until Ask integration phase."""
    import re
    terms = {term for term in re.findall(r"[a-z0-9]{3,}", query.casefold())}
    scored = []
    for section in note_payload.get("sectionNotes", []):
        text = " ".join([str(section.get("title", "")), str(section.get("bigIdea", "")), *map(str, section.get("keyTakeaways", []))])
        score = len(terms & set(re.findall(r"[a-z0-9]{3,}", text.casefold())))
        scored.append((score, section))
    selected = [item for item in sorted(scored, key=lambda item: item[0], reverse=True) if item[0] > 0][:limit]
    return {"text": "\n\n".join(str(item[1].get("bigIdea", "")) for item in selected),
        "sourceSectionIds": [str(item[1].get("id")) for item in selected],
        "sourceBlockIds": [str(block) for item in selected for block in item[1].get("sourceBlockIds", [])]}
