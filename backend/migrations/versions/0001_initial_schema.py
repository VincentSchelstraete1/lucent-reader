"""Initial Lucent library schema."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("sources",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("type", sa.String(50), nullable=False),
        sa.Column("url", sa.String(255), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("documents",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False), sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("notes",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False), sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("source_url", sa.String(255), nullable=True), sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("quizzes",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False), sa.Column("questions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("quiz_attempts",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("quiz_id", sa.Integer(), sa.ForeignKey("quizzes.id"), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False), sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))

def downgrade() -> None:
    op.drop_table("quiz_attempts"); op.drop_table("quizzes"); op.drop_table("notes"); op.drop_table("documents"); op.drop_table("sources")
