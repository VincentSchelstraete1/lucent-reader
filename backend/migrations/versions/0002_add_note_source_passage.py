"""Retain the originating passage for generated results."""
from alembic import op
import sqlalchemy as sa

revision = "0002_note_source_passage"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("notes", sa.Column("source_passage", sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column("notes", "source_passage")
