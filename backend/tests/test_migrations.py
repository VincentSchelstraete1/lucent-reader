import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg import sql
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session
from dataclasses import replace
import pytest


def test_alembic_upgrade_head_on_empty_database():
    original_url = os.environ["DATABASE_URL"]
    sqlalchemy_parts = urlsplit(original_url)
    parts = urlsplit(original_url.replace("postgresql+psycopg://", "postgresql://"))
    database_name = f"{parts.path.lstrip('/')}_migrations"
    admin_url = urlunsplit(parts._replace(path="/postgres"))
    migration_url = urlunsplit(sqlalchemy_parts._replace(path=f"/{database_name}"))
    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database_name)))
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
    try:
        os.environ["DATABASE_URL"] = migration_url
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        command.upgrade(config, "head")
        engine = create_engine(migration_url)
        try:
            tables = set(inspect(engine).get_table_names())
            assert {"users", "web_sessions", "sources", "extension_grants", "extension_refresh_tokens"} <= tables
        finally:
            engine.dispose()
    finally:
        os.environ["DATABASE_URL"] = original_url
        with psycopg.connect(admin_url, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database_name)))


def test_explicit_verified_user_legacy_claim_is_idempotent(monkeypatch):
    import app.routers.auth as auth_router
    from app.models.auth import User
    from app.security import utcnow

    original_url = os.environ["DATABASE_URL"]
    sqlalchemy_parts = urlsplit(original_url)
    parts = urlsplit(original_url.replace("postgresql+psycopg://", "postgresql://"))
    database_name = f"{parts.path.lstrip('/')}_legacy_claim"
    admin_url = urlunsplit(parts._replace(path="/postgres"))
    migration_url = urlunsplit(sqlalchemy_parts._replace(path=f"/{database_name}"))
    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database_name)))
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
    try:
        os.environ["DATABASE_URL"] = migration_url
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        command.upgrade(config, "30c016012cb8")
        engine = create_engine(migration_url)
        with engine.begin() as connection:
            source_id = connection.execute(text("INSERT INTO sources (type, url, created_at) VALUES ('website', 'https://legacy.example', :now) RETURNING id"), {"now": utcnow()}).scalar_one()
            document_id = connection.execute(text("INSERT INTO documents (source_id, title, content, created_at, updated_at) VALUES (:source, 'Legacy', 'text', :now, :now) RETURNING id"), {"source": source_id, "now": utcnow()}).scalar_one()
            connection.execute(text("INSERT INTO notes (title, content, content_type, document_id, created_at, updated_at) VALUES ('Legacy', 'note', 'highlight', :document, :now, :now)"), {"document": document_id, "now": utcnow()})
        command.upgrade(config, "0003_auth_ownership")
        monkeypatch.setattr(auth_router, "settings", replace(auth_router.settings, environment="development", enable_legacy_claim=True))
        with Session(engine) as db:
            owner = User(provider="google", provider_subject="verified-owner", email_verified=True)
            db.add(owner); db.flush()
            auth_router._claim_legacy_once(db, owner); db.commit()
            owner_id = owner.id
            auth_router._claim_legacy_once(db, owner); db.commit()
            other = User(provider="google", provider_subject="different-user", email_verified=True)
            db.add(other); db.flush()
            with pytest.raises(Exception) as conflict:
                auth_router._claim_legacy_once(db, other)
            assert getattr(conflict.value, "status_code", None) == 409
            db.rollback()
        with engine.connect() as connection:
            assert connection.execute(text("SELECT user_id FROM sources WHERE id=:id"), {"id": source_id}).scalar_one() == owner_id
            assert connection.execute(text("SELECT count(*) FROM documents WHERE source_id=:id"), {"id": source_id}).scalar_one() == 1
            assert connection.execute(text("SELECT count(*) FROM notes WHERE document_id=:id"), {"id": document_id}).scalar_one() == 1
        engine.dispose()
        command.upgrade(config, "head")
        engine = create_engine(migration_url)
        assert any(c["name"] == "user_id" and not c["nullable"] for c in inspect(engine).get_columns("sources"))
        engine.dispose()
    finally:
        os.environ["DATABASE_URL"] = original_url
        with psycopg.connect(admin_url, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database_name)))
