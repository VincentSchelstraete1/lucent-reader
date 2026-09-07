"""repair notes tags column

Revision ID: 30c016012cb8
Revises: 0002_note_source_passage
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '30c016012cb8'
down_revision: Union[str, Sequence[str], None] = '0002_note_source_passage'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Some early development databases missed this column even though the
    # baseline migration declares it. Keep this repair safe on clean installs.
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("notes")}
    if "tags" not in columns:
        op.add_column('notes', sa.Column('tags', sa.JSON(), nullable=True))

def downgrade() -> None:
    # The baseline owns the column, so downgrading the repair is intentionally
    # a no-op rather than destroying a baseline column.
    pass
