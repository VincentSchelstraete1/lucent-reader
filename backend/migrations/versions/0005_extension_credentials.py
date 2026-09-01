"""Add isolated Chrome extension credential lifecycle."""
from alembic import op
import sqlalchemy as sa

revision = "0005_extension_credentials"
down_revision = "0004_enforce_ownership"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("extension_grants",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_extension_grants_user_id", "extension_grants", ["user_id"])
    op.create_table("extension_authorization_codes",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False, unique=True), sa.Column("code_challenge", sa.String(128), nullable=False),
        sa.Column("redirect_uri", sa.String(512), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("used_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_extension_authorization_codes_code_hash", "extension_authorization_codes", ["code_hash"], unique=True)
    op.create_table("extension_access_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("grant_id", sa.Uuid(), sa.ForeignKey("extension_grants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_extension_access_tokens_grant_id", "extension_access_tokens", ["grant_id"])
    op.create_index("ix_extension_access_tokens_token_hash", "extension_access_tokens", ["token_hash"], unique=True)
    op.create_table("extension_refresh_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("grant_id", sa.Uuid(), sa.ForeignKey("extension_grants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True), sa.Column("replaced_by_id", sa.Uuid(), sa.ForeignKey("extension_refresh_tokens.id"), nullable=True))
    op.create_index("ix_extension_refresh_tokens_grant_id", "extension_refresh_tokens", ["grant_id"])
    op.create_index("ix_extension_refresh_tokens_token_hash", "extension_refresh_tokens", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_table("extension_refresh_tokens"); op.drop_table("extension_access_tokens"); op.drop_table("extension_authorization_codes"); op.drop_table("extension_grants")
