"""Store structured adaptive Learn evaluations and session reports."""
from alembic import op
import sqlalchemy as sa

revision = "0007_adaptive_learn_evidence"
down_revision = "0006_learn_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("learn_sessions", sa.Column("ended_reason", sa.String(80), nullable=True))
    op.add_column("learn_sessions", sa.Column("report", sa.JSON(), nullable=True))
    op.add_column("learn_attempts", sa.Column("evaluation", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("learn_attempts", "evaluation")
    op.drop_column("learn_sessions", "report")
    op.drop_column("learn_sessions", "ended_reason")
