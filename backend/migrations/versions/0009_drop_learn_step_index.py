"""Converge Learn sessions onto persisted LearningScene state.

The cursor is removed only after all active/stopped sessions have been
normalized by the runtime backfill.  The precondition is intentionally strict
so an upgrade cannot strand a learner in the legacy progression path.
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_drop_learn_step_index"
down_revision = "0008_learn_tutor_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    remaining = bind.execute(sa.text("SELECT count(*) FROM learn_sessions WHERE status IN ('active','stopped') AND (state IS NULL OR COALESCE((state->>'runtimeVersion')::int, 0) < 2)" )).scalar_one()
    if remaining:
        raise RuntimeError(f"Cannot remove learn_sessions.step_index: {remaining} sessions still require runtime-v2 backfill")
    op.drop_column("learn_sessions", "step_index")


def downgrade() -> None:
    op.add_column("learn_sessions", sa.Column("step_index", sa.Integer(), nullable=True))
