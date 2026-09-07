"""Persist bounded tutor telemetry for Ask Lucent and adaptive decisions."""
from alembic import op
import sqlalchemy as sa

revision = "0008_learn_tutor_events"
down_revision = "0007_adaptive_learn_evidence"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "learn_tutor_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("learn_sessions.id", ondelete="CASCADE"), nullable=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=True),
        sa.Column("event_type", sa.String(48), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for name, column in [("user_id", "user_id"), ("session_id", "session_id"), ("document_id", "document_id"), ("event_type", "event_type"), ("created_at", "created_at")]:
        op.create_index(f"ix_learn_tutor_events_{name}", "learn_tutor_events", [column])

def downgrade() -> None:
    op.drop_table("learn_tutor_events")
