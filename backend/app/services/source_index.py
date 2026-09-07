from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import os
import re
import time
import uuid
from typing import Any

from sqlalchemy import delete, select

from app.models.learn import LearnSession
from app.models.learning_block import DocumentSourceIndex, PersistedLearningBlock
from app.database import SessionLocal
from app.services.embeddings import EmbeddingError, get_embedding_provider


logger = logging.getLogger(__name__)

EMBEDDING_INPUT_VERSION = "learning-block-input-v1"
DEFAULT_EMBEDDING_PROVIDER = "voyage"
DEFAULT_EMBEDDING_MODEL = "voyage-3-lite"
DEFAULT_EMBEDDING_DIMENSIONS = 512

_DIAGNOSTIC_PATTERNS = (
    "insufficient source",
    "no substantive content",
    "extraction error",
    "unable to extract",
    "could not extract",
    "metadata header",
    "source material unavailable",
    "document contains no text",
    "unable to design a learning experience",
)


class SourceCorpusInvalid(ValueError):
    """The extracted representation is not safe or substantive enough to teach."""


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _is_diagnostic(text: str) -> bool:
    lowered = text.casefold()
    return any(pattern in lowered for pattern in _DIAGNOSTIC_PATTERNS)


def _substantive_words(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]+", text.casefold()) if len(word) > 2}


def _bounded_attachment(record: dict[str, Any]) -> dict[str, Any]:
    """Retain source-resolvable text/metadata without persisting image bytes."""
    allowed = {
        "id",
        "type",
        "text",
        "source",
        "source_image_id",
        "source_page",
        "source_bbox",
        "width",
        "height",
        "mime_type",
        "caption",
        "source_image_ids",
        "location",
    }
    result = {key: record[key] for key in allowed if key in record}
    result.pop("asset_reference", None)
    if isinstance(result.get("text"), str):
        result["text"] = result["text"][:3000]
    if isinstance(result.get("caption"), str):
        result["caption"] = result["caption"][:1000]
    return result


def embedding_input_for(block: dict[str, Any]) -> str:
    parts = [
        _clean(block.get("title")),
        " > ".join(_clean(item) for item in block.get("heading_ancestry", []) if _clean(item)),
        _clean(block.get("text")),
    ]
    for attachment in block.get("attachments", []):
        parts.extend((_clean(attachment.get("text")), _clean(attachment.get("caption"))))
    text = "\n".join(part for part in parts if part)
    encoded = text.encode("utf-8")
    if len(encoded) <= 6000:
        return text
    return encoded[:6000].decode("utf-8", errors="ignore").rsplit(" ", 1)[0].strip()


def corpus_records(response) -> tuple[list[dict[str, Any]], list[str]]:
    normalized = response.normalized.model_dump(mode="json")
    normalized_blocks = {
        item["id"]: item
        for page in normalized.get("pages", [])
        for item in page.get("blocks", [])
        if isinstance(item, dict) and item.get("id")
    }
    normalized_images = {
        item["id"]: item for item in normalized.get("images", []) if isinstance(item, dict) and item.get("id")
    }
    sections_by_block: dict[str, list[str]] = defaultdict(list)
    for section in response.section_notes:
        for block_id in section.source_block_ids:
            sections_by_block[str(block_id)].append(str(section.id))

    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    for ordinal, block_model in enumerate(response.learning_blocks):
        block = block_model.model_dump(mode="json")
        attachments = [
            _bounded_attachment(normalized_blocks[item])
            for item in block.get("attached_table_ids", [])
            if item in normalized_blocks
        ]
        attachments.extend(
            _bounded_attachment(normalized_images[item])
            for item in block.get("attached_image_ids", [])
            if item in normalized_images
        )
        record = {
            "block_id": str(block["id"]),
            "ordinal": ordinal,
            "block_type": str(block["block_type"]),
            "title": block.get("title"),
            "text": _clean(block.get("text")),
            "character_count": len(_clean(block.get("text"))),
            "token_count": block.get("token_count"),
            "heading_ancestry": [str(item) for item in block.get("heading_ancestry", [])],
            "normalized_block_ids": [str(item) for item in block.get("normalized_block_ids", [])],
            "section_ids": sorted(set(sections_by_block.get(str(block["id"]), []))),
            "source": block.get("source") or {},
            "segmentation": {
                "method": block.get("segmentation_method"),
                "boundary_reason": block.get("segmentation_boundary_reason"),
                "version": "segmentation-v1",
                "confidence": block.get("segmentation_confidence"),
            },
            "attachments": attachments,
        }
        input_text = embedding_input_for(record)
        record["content_hash"] = _sha256({key: record[key] for key in record if key != "segmentation"})
        record["embedding_input_hash"] = hashlib.sha256(input_text.encode("utf-8")).hexdigest()
        records.append(record)

        missing = set(block.get("attached_table_ids", [])) - set(normalized_blocks)
        missing |= set(block.get("attached_image_ids", [])) - set(normalized_images)
        if missing:
            warnings.append(f"unresolved_attachments:{record['block_id']}:{len(missing)}")

    usable = [embedding_input_for(record) for record in records]
    usable = [text for text in usable if text and not _is_diagnostic(text)]
    joined = " ".join(usable)
    if not records or len(joined) < 20 or len(_substantive_words(joined)) < 3:
        raise SourceCorpusInvalid("The extracted source does not contain enough substantive material to learn from.")
    if not usable:
        raise SourceCorpusInvalid("The extracted source contains diagnostics rather than learnable material.")
    return records, sorted(set(warnings))


def persist_source_corpus(db, *, document_id: int, response) -> DocumentSourceIndex:
    records, warnings = corpus_records(response)
    normalization_version = response.normalized.normalization_metadata.version
    segmentation_versions = sorted({str(item["segmentation"]["version"]) for item in records})
    segmentation_version = ",".join(segmentation_versions)
    canonical = {
        "normalization_version": normalization_version,
        "segmentation_version": segmentation_version,
        "embedding_input_version": EMBEDDING_INPUT_VERSION,
        "records": records,
    }
    corpus_hash = _sha256(canonical)
    existing = db.get(DocumentSourceIndex, document_id)
    if existing is not None and existing.corpus_hash == corpus_hash:
        return existing

    now = datetime.now(timezone.utc)
    generation_id = uuid.uuid4()
    if existing is None:
        index = DocumentSourceIndex(
            document_id=document_id,
            generation_id=generation_id,
            corpus_hash=corpus_hash,
            normalization_version=normalization_version,
            segmentation_version=segmentation_version,
            embedding_input_version=EMBEDDING_INPUT_VERSION,
            status="PENDING",
            provider=DEFAULT_EMBEDDING_PROVIDER,
            model=DEFAULT_EMBEDDING_MODEL,
            dimensions=DEFAULT_EMBEDDING_DIMENSIONS,
            block_count=len(records),
            embedded_count=0,
            attempt_count=0,
            coverage_warnings=warnings,
        )
        db.add(index)
        db.flush()
    else:
        index = existing
        db.execute(delete(PersistedLearningBlock).where(PersistedLearningBlock.document_id == document_id))
        index.generation_id = generation_id
        index.corpus_hash = corpus_hash
        index.normalization_version = normalization_version
        index.segmentation_version = segmentation_version
        index.embedding_input_version = EMBEDDING_INPUT_VERSION
        index.status = "PENDING"
        index.block_count = len(records)
        index.embedded_count = 0
        index.attempt_id = None
        index.lease_expires_at = None
        index.failure_code = None
        index.coverage_warnings = warnings
        index.indexed_at = None
        index.updated_at = now

        sessions = db.execute(
            select(LearnSession).where(
                LearnSession.document_id == document_id,
                LearnSession.status.in_(("active", "stopped")),
            )
        ).scalars()
        for session in sessions:
            state = dict(session.state or {})
            state["sourceInvalidated"] = True
            state["sourceInvalidatedAt"] = now.isoformat()
            session.state = state
            session.status = "stopped"
            session.ended_reason = "source_updated"

    for record in records:
        db.add(PersistedLearningBlock(document_id=document_id, generation_id=generation_id, **record))
    db.flush()
    return index


def index_document(document_id: int, generation_id: uuid.UUID) -> bool:
    """Embed and atomically publish one immutable corpus generation."""
    attempt_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    started = time.perf_counter()
    with SessionLocal.begin() as db:
        source_index = db.get(DocumentSourceIndex, document_id, with_for_update=True)
        if source_index is None or source_index.generation_id != generation_id:
            logger.warning(
                "source_index_skipped document_id=%s generation_id=%s reason=%s",
                document_id, generation_id, "missing" if source_index is None else "generation_mismatch",
            )
            return False
        lease_active = source_index.status == "INDEXING" and source_index.lease_expires_at and source_index.lease_expires_at > now
        if lease_active or source_index.status == "READY":
            logger.warning(
                "source_index_skipped document_id=%s generation_id=%s reason=%s status=%s",
                document_id, generation_id, "lease_active" if lease_active else "already_ready", source_index.status,
            )
            return False
        logger.info(
            "source_index_started document_id=%s generation_id=%s attempt_id=%s attempt_count=%s block_count=%s",
            document_id, generation_id, attempt_id, source_index.attempt_count + 1, source_index.block_count,
        )
        source_index.status = "INDEXING"
        source_index.attempt_id = attempt_id
        source_index.attempt_count += 1
        source_index.lease_expires_at = now + timedelta(minutes=5)
        source_index.failure_code = None

    try:
        provider = get_embedding_provider()
        with SessionLocal() as db:
            rows = db.execute(
                select(PersistedLearningBlock)
                .where(
                    PersistedLearningBlock.document_id == document_id,
                    PersistedLearningBlock.generation_id == generation_id,
                )
                .order_by(PersistedLearningBlock.ordinal)
            ).scalars().all()
            inputs = [
                embedding_input_for(
                    {
                        "title": row.title,
                        "heading_ancestry": row.heading_ancestry,
                        "text": row.text,
                        "attachments": row.attachments,
                    }
                )
                for row in rows
            ]
        if not rows:
            raise SourceCorpusInvalid("No source blocks are available for indexing")
        batch_size = max(1, min(int(os.getenv("RAG_EMBEDDING_BATCH_SIZE", "32")), 128))
        vectors: list[list[float]] = []
        for offset in range(0, len(inputs), batch_size):
            vectors.extend(provider.embed_documents(inputs[offset : offset + batch_size]))
            with SessionLocal.begin() as db:
                source_index = db.get(DocumentSourceIndex, document_id, with_for_update=True)
                if (
                    source_index is None
                    or source_index.generation_id != generation_id
                    or source_index.attempt_id != attempt_id
                ):
                    return False
                source_index.lease_expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        if len(vectors) != len(rows):
            raise EmbeddingError("Embedding provider returned an incomplete corpus")

        published_at = datetime.now(timezone.utc)
        with SessionLocal.begin() as db:
            source_index = db.get(DocumentSourceIndex, document_id, with_for_update=True)
            if (
                source_index is None
                or source_index.generation_id != generation_id
                or source_index.attempt_id != attempt_id
            ):
                return False
            current_rows = db.execute(
                select(PersistedLearningBlock)
                .where(
                    PersistedLearningBlock.document_id == document_id,
                    PersistedLearningBlock.generation_id == generation_id,
                )
                .order_by(PersistedLearningBlock.ordinal)
            ).scalars().all()
            if len(current_rows) != len(vectors):
                return False
            for row, vector in zip(current_rows, vectors):
                row.embedding = vector
                row.embedded_at = published_at
            source_index.provider = provider.metadata.provider
            source_index.model = provider.metadata.model
            source_index.dimensions = provider.metadata.dimensions
            source_index.status = "READY"
            source_index.embedded_count = len(vectors)
            source_index.failure_code = None
            source_index.lease_expires_at = None
            source_index.indexed_at = published_at
        logger.info(
            "source_index_ready document_id=%s generation_id=%s provider=%s model=%s dimensions=%s embedded=%s duration_ms=%.1f",
            document_id, generation_id, provider.metadata.provider, provider.metadata.model,
            provider.metadata.dimensions, len(vectors), (time.perf_counter() - started) * 1000,
        )
        return True
    except (EmbeddingError, SourceCorpusInvalid) as exc:
        with SessionLocal.begin() as db:
            source_index = db.get(DocumentSourceIndex, document_id, with_for_update=True)
            if (
                source_index is not None
                and source_index.generation_id == generation_id
                and source_index.attempt_id == attempt_id
            ):
                source_index.status = "FAILED"
                source_index.failure_code = getattr(exc, "code", "source_invalid")
                source_index.lease_expires_at = None
        logger.error(
            "source_index_failed document_id=%s generation_id=%s attempt_id=%s failure_code=%s exception=%s duration_ms=%.1f",
            document_id, generation_id, attempt_id, getattr(exc, "code", "source_invalid"),
            type(exc).__name__, (time.perf_counter() - started) * 1000,
        )
        return False
