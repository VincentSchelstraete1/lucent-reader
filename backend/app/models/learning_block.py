from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DocumentSourceIndex(Base):
    __tablename__ = "document_source_indexes"
    __table_args__ = (
        CheckConstraint("status IN ('PENDING', 'INDEXING', 'READY', 'FAILED')", name="ck_document_source_indexes_status"),
        CheckConstraint("dimensions > 0", name="ck_document_source_indexes_dimensions"),
        CheckConstraint("block_count >= 0", name="ck_document_source_indexes_block_count"),
        CheckConstraint("embedded_count >= 0 AND embedded_count <= block_count", name="ck_document_source_indexes_embedded_count"),
        CheckConstraint("attempt_count >= 0", name="ck_document_source_indexes_attempt_count"),
    )

    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    generation_id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, nullable=False)
    corpus_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    normalization_version: Mapped[str] = mapped_column(String(80), nullable=False)
    segmentation_version: Mapped[str] = mapped_column(String(80), nullable=False)
    embedding_input_version: Mapped[str] = mapped_column(String(80), default="learning-block-input-v1", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(48), default="voyage", nullable=False)
    model: Mapped[str] = mapped_column(String(80), default="voyage-3-lite", nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, default=512, nullable=False)
    block_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    embedded_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    coverage_warnings: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    blocks: Mapped[list["PersistedLearningBlock"]] = relationship(
        back_populates="source_index", cascade="all, delete-orphan", passive_deletes=True
    )


class PersistedLearningBlock(Base):
    __tablename__ = "learning_blocks"
    __table_args__ = (
        UniqueConstraint("document_id", "ordinal", name="uq_learning_blocks_document_ordinal"),
        CheckConstraint("ordinal >= 0", name="ck_learning_blocks_ordinal"),
        CheckConstraint("character_count >= 0", name="ck_learning_blocks_character_count"),
    )

    document_id: Mapped[int] = mapped_column(
        ForeignKey("document_source_indexes.document_id", ondelete="CASCADE"), primary_key=True
    )
    block_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    generation_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    block_type: Mapped[str] = mapped_column(String(24), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heading_ancestry: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    normalized_block_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    section_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    source: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    segmentation: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    attachments: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    source_index: Mapped[DocumentSourceIndex] = relationship(back_populates="blocks")
