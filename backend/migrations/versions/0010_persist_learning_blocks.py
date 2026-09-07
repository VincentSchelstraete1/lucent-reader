"""Persist the authoritative source corpus and embedding-index lifecycle."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0010_persist_learning_blocks"
down_revision = "0009_drop_learn_step_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_source_indexes",
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("generation_id", sa.Uuid(), nullable=False),
        sa.Column("corpus_hash", sa.String(64), nullable=False),
        sa.Column("normalization_version", sa.String(80), nullable=False),
        sa.Column("segmentation_version", sa.String(80), nullable=False),
        sa.Column("embedding_input_version", sa.String(80), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(48), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("block_count", sa.Integer(), nullable=False),
        sa.Column("embedded_count", sa.Integer(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("coverage_warnings", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('PENDING', 'INDEXING', 'READY', 'FAILED')", name="ck_document_source_indexes_status"),
        sa.CheckConstraint("dimensions > 0", name="ck_document_source_indexes_dimensions"),
        sa.CheckConstraint("block_count >= 0", name="ck_document_source_indexes_block_count"),
        sa.CheckConstraint("embedded_count >= 0 AND embedded_count <= block_count", name="ck_document_source_indexes_embedded_count"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_document_source_indexes_attempt_count"),
    )
    op.create_index("ix_document_source_indexes_status", "document_source_indexes", ["status"])
    op.create_index("ix_document_source_indexes_lease_expires_at", "document_source_indexes", ["lease_expires_at"])
    op.create_table(
        "learning_blocks",
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("document_source_indexes.document_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("block_id", sa.String(160), primary_key=True),
        sa.Column("generation_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("block_type", sa.String(24), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("heading_ancestry", postgresql.JSONB(), nullable=False),
        sa.Column("normalized_block_ids", postgresql.JSONB(), nullable=False),
        sa.Column("section_ids", postgresql.JSONB(), nullable=False),
        sa.Column("source", postgresql.JSONB(), nullable=False),
        sa.Column("segmentation", postgresql.JSONB(), nullable=False),
        sa.Column("attachments", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("embedding_input_hash", sa.String(64), nullable=False),
        sa.Column("embedding", postgresql.JSONB(), nullable=True),
        sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("document_id", "ordinal", name="uq_learning_blocks_document_ordinal"),
        sa.CheckConstraint("ordinal >= 0", name="ck_learning_blocks_ordinal"),
        sa.CheckConstraint("character_count >= 0", name="ck_learning_blocks_character_count"),
    )
    op.create_index("ix_learning_blocks_generation_id", "learning_blocks", ["generation_id"])


def downgrade() -> None:
    op.drop_table("learning_blocks")
    op.drop_table("document_source_indexes")
