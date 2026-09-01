"""Enforce final non-null ownership after explicit legacy claim."""
from alembic import op
import sqlalchemy as sa

revision = "0004_enforce_ownership"
down_revision = "0003_auth_ownership"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    unowned_sources = bind.execute(sa.text("SELECT count(*) FROM sources WHERE user_id IS NULL")).scalar_one()
    if unowned_sources:
        raise RuntimeError(
            "Legacy Sources remain unowned. Run the verified development Google legacy claim at revision "
            "0003_auth_ownership, disable ENABLE_LEGACY_CLAIM, then rerun this migration."
        )
    bind.execute(sa.text("""
        UPDATE quiz_attempts AS attempt
        SET user_id = source.user_id
        FROM quizzes AS quiz
        JOIN documents AS document ON document.id = quiz.document_id
        JOIN sources AS source ON source.id = document.source_id
        WHERE attempt.quiz_id = quiz.id AND attempt.user_id IS NULL
    """))
    if bind.execute(sa.text("SELECT count(*) FROM quiz_attempts WHERE user_id IS NULL")).scalar_one():
        raise RuntimeError("Quiz attempts remain unowned; resolve them explicitly before enforcing ownership")
    op.alter_column("sources", "user_id", existing_type=sa.Uuid(), nullable=False)
    op.alter_column("quiz_attempts", "user_id", existing_type=sa.Uuid(), nullable=False)


def downgrade() -> None:
    op.alter_column("quiz_attempts", "user_id", existing_type=sa.Uuid(), nullable=True)
    op.alter_column("sources", "user_id", existing_type=sa.Uuid(), nullable=True)
