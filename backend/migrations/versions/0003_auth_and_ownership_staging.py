"""Add users, web authentication, and staged ownership.

Existing sources remain NULL only long enough for the explicitly enabled,
verified-Google legacy claim. Upgrade 0004 enforces the final constraints.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_auth_ownership"
down_revision = "30c016012cb8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_subject", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_subject", name="uq_users_provider_subject"),
    )
    op.create_table(
        "web_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("credential_hash", sa.String(64), nullable=False),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("credential_hash"),
    )
    op.create_index("ix_web_sessions_user_id", "web_sessions", ["user_id"])
    op.create_index("ix_web_sessions_credential_hash", "web_sessions", ["credential_hash"], unique=True)
    op.create_table(
        "oauth_transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("state_hash", sa.String(64), nullable=False),
        sa.Column("code_verifier", sa.String(128), nullable=False),
        sa.Column("nonce", sa.String(128), nullable=False),
        sa.Column("flow_type", sa.String(32), nullable=False),
        sa.Column("return_to", sa.String(255), nullable=False),
        sa.Column("extension_state", sa.String(128), nullable=True),
        sa.Column("extension_redirect_uri", sa.String(512), nullable=True),
        sa.Column("extension_code_challenge", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("state_hash"),
    )
    op.create_index("ix_oauth_transactions_state_hash", "oauth_transactions", ["state_hash"], unique=True)
    op.create_table(
        "legacy_claims",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.add_column("sources", sa.Column("user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_sources_user_id", "sources", "users", ["user_id"], ["id"])
    op.create_index("ix_sources_user_id", "sources", ["user_id"])
    op.create_unique_constraint("uq_sources_user_type_url", "sources", ["user_id", "type", "url"])
    op.add_column("quiz_attempts", sa.Column("user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_quiz_attempts_user_id", "quiz_attempts", "users", ["user_id"], ["id"])
    op.create_index("ix_quiz_attempts_user_id", "quiz_attempts", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_quiz_attempts_user_id", table_name="quiz_attempts")
    op.drop_constraint("fk_quiz_attempts_user_id", "quiz_attempts", type_="foreignkey")
    op.drop_column("quiz_attempts", "user_id")
    op.drop_constraint("uq_sources_user_type_url", "sources", type_="unique")
    op.drop_index("ix_sources_user_id", table_name="sources")
    op.drop_constraint("fk_sources_user_id", "sources", type_="foreignkey")
    op.drop_column("sources", "user_id")
    op.drop_table("legacy_claims")
    op.drop_index("ix_oauth_transactions_state_hash", table_name="oauth_transactions")
    op.drop_table("oauth_transactions")
    op.drop_index("ix_web_sessions_credential_hash", table_name="web_sessions")
    op.drop_index("ix_web_sessions_user_id", table_name="web_sessions")
    op.drop_table("web_sessions")
    op.drop_table("users")
