"""Authoritative, document-scoped retrieval of persisted original source blocks."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import json
import logging
import os
import time
from typing import Any, Sequence
import uuid

from sqlalchemy import select

from app.models.document import Document
from app.models.learning_block import DocumentSourceIndex, PersistedLearningBlock
from app.models.source import Source
from app.services.embeddings import EmbeddingError, get_embedding_provider
from app.services.source_index import embedding_input_for


logger = logging.getLogger(__name__)

QUERY_VERSION = "source-query-v1"
RETRIEVAL_VERSION = "exact-cosine-v1"
RETRIEVAL_POLICY_VERSION = "rag-retrieval-policy-v1"
# Calibrated on the locked Stage 2 development split for voyage-3-lite,
# 512 dimensions, learning-block-input-v1, and QUERY_VERSION above.
DEFAULT_MIN_SIMILARITY = 0.50556
CALIBRATED_PROVIDER = "voyage"
CALIBRATED_MODEL = "voyage-3-lite"
CALIBRATED_DIMENSIONS = 512


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
    raw_ranked_block_ids: list[str] = field(default_factory=list)
    raw_ranked_scores: list[float] = field(default_factory=list)
    omitted_block_ids: list[str] = field(default_factory=list)
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
    log = logger.error if status in {RetrievalStatus.FAILED} else logger.warning
    log(
        "retrieval_unavailable document_id=%s status=%s generation_id=%s fingerprint=%s failure_code=%s",
        document_id, status.value, generation_id, fingerprint, failure_code,
    )
    return RetrievedSourceContext(status=status, document_id=document_id, generation_id=generation_id,
        query_fingerprint=fingerprint, provider=index.provider if index else None,
        model=index.model if index else None, dimensions=index.dimensions if index else None,
        failure_code=failure_code)


def retrieve_source(db, *, user_id: uuid.UUID, document_id: int, expected_generation: uuid.UUID | None,
                    query: SourceQuery, anchor_block_ids: Sequence[str] = (), top_k: int = 5,
                    min_similarity: float | None = None) -> RetrievedSourceContext:
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
    except EmbeddingError as exc:
        logger.error(
            "retrieval_embedding_failed document_id=%s fingerprint=%s purpose=%s exception=%s code=%s",
            document_id, fingerprint, query.purpose, type(exc).__name__, getattr(exc, "code", "embedding_error"),
        )
        return _empty_context(RetrievalStatus.FAILED, document_id=document_id,
            generation_id=source_index.generation_id, fingerprint=fingerprint, index=source_index,
            failure_code="embedding_unavailable")
    embedding_ms = (time.perf_counter() - embedding_started) * 1000

    search_started = time.perf_counter()
    scored: list[tuple[float, PersistedLearningBlock]] = []
    for row in rows:
        if not isinstance(row.embedding, list):
            continue
        try:
            scored.append((exact_cosine(query_vector, row.embedding), row))
        except (TypeError, ValueError):
            continue
    scored.sort(key=lambda item: (-item[0], item[1].ordinal, item[1].block_id))
    raw_ranked_block_ids = [row.block_id for _, row in scored]
    raw_ranked_scores = [score for score, _ in scored]
    semantic_limit = max(0, min(int(top_k), 8) - len(selected))
    selected.extend(
        (row, score, "semantic")
        for score, row in [(score, row) for score, row in scored if row.block_id not in seen][:semantic_limit]
    )
    search_ms = (time.perf_counter() - search_started) * 1000

    output: list[RetrievedSourceBlock] = []
    used = 0
    truncated = False
    for row, score, selection in selected[:8]:
        excerpt = embedding_input_for({"title": row.title, "heading_ancestry": row.heading_ancestry,
                                       "text": row.text, "attachments": row.attachments}).strip()
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

    if min_similarity is None:
        threshold_text = os.getenv("RAG_MIN_SIMILARITY", "").strip()
        calibrated_index = (
            source_index.provider == CALIBRATED_PROVIDER
            and source_index.model == CALIBRATED_MODEL
            and source_index.dimensions == CALIBRATED_DIMENSIONS
        )
        threshold = (
            float(threshold_text)
            if threshold_text
            else DEFAULT_MIN_SIMILARITY if calibrated_index else -1.0
        )
    else:
        threshold = float(min_similarity)
    if not -1.0 <= threshold <= 1.0:
        raise ValueError("RAG minimum similarity must be between -1 and 1")
    semantic_scores = [block.score for block in output if block.score is not None]
    status = RetrievalStatus.SUPPORTED if output else RetrievalStatus.WEAK
    if semantic_scores and max(semantic_scores) < threshold and not any(block.selection == "anchor" for block in output):
        status = RetrievalStatus.WEAK
    selected_ids = {block_id for block in output for block_id in block.block_ids}
    top_score = max(semantic_scores) if semantic_scores else None
    (logger.info if status == RetrievalStatus.SUPPORTED else logger.warning)(
        "retrieval_complete document_id=%s status=%s purpose=%s fingerprint=%s corpus_blocks=%s "
        "returned=%s top_score=%s threshold=%.5f truncated=%s coverage_incomplete=%s "
        "embedding_ms=%.1f search_ms=%.1f total_ms=%.1f",
        document_id, status.value, query.purpose, fingerprint, len(rows), len(output),
        f"{top_score:.5f}" if top_score is not None else "none", threshold, truncated, missing_anchor,
        embedding_ms, search_ms, (time.perf_counter() - started) * 1000,
    )
    return RetrievedSourceContext(status=status, document_id=document_id, generation_id=source_index.generation_id,
        query_fingerprint=fingerprint, provider=source_index.provider, model=source_index.model,
        dimensions=source_index.dimensions, blocks=output, raw_ranked_block_ids=raw_ranked_block_ids,
        raw_ranked_scores=raw_ranked_scores,
        omitted_block_ids=[block_id for block_id in raw_ranked_block_ids if block_id not in selected_ids],
        coverage_incomplete=missing_anchor,
        truncated=truncated, timings_ms={"query_embedding": embedding_ms, "search": search_ms,
                                        "total": (time.perf_counter() - started) * 1000})


def serialize_source_context(context: RetrievedSourceContext, *, max_chars: int = 8000) -> str:
    payload = [{"blockIds": block.block_ids, "sectionIds": block.section_ids,
                "source": block.source, "text": block.text} for block in context.blocks]
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    while len(encoded) > max_chars and len(payload) > 1:
        payload.pop()
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(encoded) > max_chars and payload:
        overhead = len(json.dumps([{**payload[0], "text": ""}], ensure_ascii=False, separators=(",", ":")))
        payload[0]["text"] = payload[0]["text"][: max(0, max_chars - overhead - 4)].rsplit(" ", 1)[0]
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return encoded
