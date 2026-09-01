import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv

# app.database/app.main read DATABASE_URL from the environment at import
# time, and load_dotenv() never overrides an already-set variable - so
# redirecting this to a separate *_test database, before any app module
# is imported below, is what keeps the whole test run off the real dev
# database. load_dotenv() here just makes sure DATABASE_URL is populated
# from backend/.env in the first place, same as the app itself does.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

_dev_url = os.environ["DATABASE_URL"]
if not urlsplit(_dev_url.replace("postgresql+psycopg://", "postgresql://")).path.endswith("_test"):
    base, _, db_name = _dev_url.rpartition("/")
    _dev_url = f"{base}/{db_name}_test"
os.environ["DATABASE_URL"] = _dev_url
os.environ["APP_ENV"] = "test"
os.environ["ALLOWED_ORIGINS"] = "http://testserver"
os.environ["API_ORIGIN"] = "http://testserver"


def _ensure_database_exists(url: str) -> None:
    import psycopg

    parts = urlsplit(url.replace("postgresql+psycopg://", "postgresql://"))
    db_name = parts.path.lstrip("/")
    admin_url = urlunsplit(parts._replace(path="/postgres"))

    conn = psycopg.connect(admin_url, autocommit=True)
    try:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (db_name,)
        ).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        conn.close()


_ensure_database_exists(os.environ["DATABASE_URL"])

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.database import Base, engine, get_db
from app.main import app  # noqa: E402 - imports models, runs create_all against the test db
from app.config import settings
from app.models.auth import User, WebSession
from app.security import token_hash, utcnow
from datetime import timedelta

# The test database is disposable. Rebuild its schema once per run so model
# changes are tested immediately; development data is migrated separately.
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

pytest_plugins = ["ai_fixtures"]

TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture()
def client():
    with TestSessionLocal() as db:
        user = User(provider="test", provider_subject="default-user", email="test@lucent.local", email_verified=True)
        db.add(user)
        db.flush()
        credential, csrf = "test-session-credential", "test-csrf-token"
        now = utcnow()
        db.add(WebSession(user_id=user.id, credential_hash=token_hash(credential), csrf_hash=token_hash(csrf), idle_expires_at=now + timedelta(hours=1), absolute_expires_at=now + timedelta(hours=2)))
        db.commit()
    test_client = TestClient(app, headers={"Origin": "http://testserver", "X-CSRF-Token": csrf})
    test_client.cookies.set(settings.session_cookie_name, credential)
    test_client.cookies.set("lucent_csrf", csrf)
    return test_client


@pytest.fixture()
def unauthenticated_client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_tables():
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
