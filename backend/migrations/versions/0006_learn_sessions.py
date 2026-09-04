"""Persist bounded Learn sessions and response signals."""
from alembic import op
import sqlalchemy as sa

revision = "0006_learn_sessions"
down_revision = "0005_extension_credentials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "learn_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("note_id", sa.Integer(), sa.ForeignKey("notes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("goal", sa.String(24), nullable=False),
        sa.Column("familiarity", sa.String(24), nullable=False),
        sa.Column("plan", sa.JSON(), nullable=False),
        sa.Column("objective_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("step_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("plan_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_learn_sessions_user_id", "learn_sessions", ["user_id"])
    op.create_index("ix_learn_sessions_document_id", "learn_sessions", ["document_id"])
    op.create_index("ix_learn_sessions_plan_fingerprint", "learn_sessions", ["plan_fingerprint"])
    op.create_table(
        "learn_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("learn_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("objective_id", sa.String(60), nullable=False),
        sa.Column("step_id", sa.String(60), nullable=False),
        sa.Column("step_type", sa.String(32), nullable=False),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column("result", sa.String(24), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("hints_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_learn_attempts_session_id", "learn_attempts", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_learn_attempts_session_id", table_name="learn_attempts")
    op.drop_table("learn_attempts")
    op.drop_index("ix_learn_sessions_plan_fingerprint", table_name="learn_sessions")
    op.drop_index("ix_learn_sessions_document_id", table_name="learn_sessions")
    op.drop_index("ix_learn_sessions_user_id", table_name="learn_sessions")
    op.drop_table("learn_sessions")
