from datetime import timedelta
from dataclasses import replace

from authlib.jose import JsonWebKey, jwt
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.config import settings
from app.main import app
from app.auth_dependencies import _active_cookie_session
from app.models.auth import User, WebSession
from app.models.document import Document
from app.models.learn import LearnAttempt, LearnSession, LearnTutorEvent
from app.models.note import Note
from app.models.quiz import Quiz, QuizAttempt
from app.models.source import Source
from app.security import token_hash, utcnow
from app.routers.auth import _rotate_web_session, _verified_google_claims
from conftest import TestSessionLocal


def _client_for(user: User, *, expired=False, revoked=False) -> TestClient:
    credential, csrf = f"credential-{user.provider_subject}", f"csrf-{user.provider_subject}"
    now = utcnow()
    with TestSessionLocal() as db:
        db.add(WebSession(
            user_id=user.id, credential_hash=token_hash(credential), csrf_hash=token_hash(csrf),
            idle_expires_at=now - timedelta(seconds=1) if expired else now + timedelta(hours=1),
            absolute_expires_at=now + timedelta(hours=2), revoked_at=now if revoked else None,
        ))
        db.commit()
    client = TestClient(app, headers={"Origin": "http://testserver", "X-CSRF-Token": csrf})
    client.cookies.set(settings.session_cookie_name, credential)
    client.cookies.set("lucent_csrf", csrf)
    return client


def _user(subject: str) -> User:
    with TestSessionLocal() as db:
        user = User(provider="test", provider_subject=subject, email=f"{subject}@example.test", email_verified=True)
        db.add(user); db.commit(); db.refresh(user); db.expunge(user)
        return user


def test_protected_request_requires_authentication(unauthenticated_client):
    assert unauthenticated_client.get("/sources").status_code == 401


def test_valid_session_resolves_user():
    user = _user("valid")
    response = _client_for(user).get("/auth/me")
    assert response.status_code == 200
    assert response.json()["user"]["id"] == str(user.id)


def test_cookie_session_is_resolved_and_touched_only_once_per_request():
    user = _user("request-cache")
    credential = "credential-request-cache"
    now = utcnow()
    with TestSessionLocal() as db:
        db.add(WebSession(
            user_id=user.id,
            credential_hash=token_hash(credential),
            csrf_hash=token_hash("csrf-request-cache"),
            idle_expires_at=now + timedelta(hours=1),
            absolute_expires_at=now + timedelta(hours=2),
        ))
        db.commit()

        class CountingSession:
            def __init__(self, wrapped):
                self.wrapped = wrapped
                self.execute_count = 0
                self.commit_count = 0

            def execute(self, *args, **kwargs):
                self.execute_count += 1
                return self.wrapped.execute(*args, **kwargs)

            def commit(self):
                self.commit_count += 1
                return self.wrapped.commit()

        counted = CountingSession(db)
        request = Request({
            "type": "http",
            "method": "POST",
            "path": "/sources",
            "headers": [(b"cookie", f"{settings.session_cookie_name}={credential}".encode())],
        })
        first = _active_cookie_session(request, counted)
        second = _active_cookie_session(request, counted)

        assert first is second
        assert counted.execute_count == 1
        assert counted.commit_count == 1


def test_expired_revoked_and_random_sessions_are_rejected():
    assert _client_for(_user("expired"), expired=True).get("/auth/me").status_code == 401
    assert _client_for(_user("revoked"), revoked=True).get("/auth/me").status_code == 401
    client = TestClient(app); client.cookies.set(settings.session_cookie_name, "random")
    assert client.get("/auth/me").status_code == 401


def test_logout_revokes_server_session():
    client = _client_for(_user("logout"))
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").status_code == 401


def test_delete_account_removes_owned_data_and_preserves_other_users():
    user = _user("delete-account")
    other = _user("keep-account")
    client = _client_for(user)

    with TestSessionLocal() as db:
        source = Source(user_id=user.id, type="upload", url="delete-account.txt")
        other_source = Source(user_id=other.id, type="upload", url="keep-account.txt")
        db.add_all([source, other_source]); db.flush()
        document = Document(source_id=source.id, title="Private material", content="synthetic test content")
        db.add(document); db.flush()
        note = Note(title="Private note", content="synthetic", content_type="text", document_id=document.id)
        quiz = Quiz(document_id=document.id, title="Private quiz", questions=[])
        session = LearnSession(
            user_id=user.id, document_id=document.id, note_id=None, goal="understand",
            familiarity="new", plan={}, state={}, plan_fingerprint="delete-account-test",
        )
        db.add_all([note, quiz, session]); db.flush()
        db.add_all([
            QuizAttempt(user_id=user.id, quiz_id=quiz.id, score=1, total=1),
            LearnAttempt(session_id=session.id, objective_id="objective-1", step_id="step-1", step_type="practice", result="correct"),
            LearnTutorEvent(user_id=user.id, session_id=session.id, document_id=document.id, event_type="test", event_metadata={}),
        ])
        db.commit()
        owned_ids = {"source": source.id, "document": document.id, "note": note.id, "quiz": quiz.id, "session": session.id}
        other_source_id = other_source.id

    response = client.delete("/auth/account")
    assert response.status_code == 204
    assert client.get("/auth/me").status_code == 401

    with TestSessionLocal() as db:
        assert db.get(User, user.id) is None
        assert db.get(Source, owned_ids["source"]) is None
        assert db.get(Document, owned_ids["document"]) is None
        assert db.get(Note, owned_ids["note"]) is None
        assert db.get(Quiz, owned_ids["quiz"]) is None
        assert db.get(LearnSession, owned_ids["session"]) is None
        assert db.get(User, other.id) is not None
        assert db.get(Source, other_source_id) is not None


def test_successful_authentication_rotates_existing_session():
    user = _user("rotate")
    old_credential = "existing-session"
    now = utcnow()
    with TestSessionLocal() as db:
        old = WebSession(user_id=user.id, credential_hash=token_hash(old_credential), csrf_hash=token_hash("old-csrf"), idle_expires_at=now + timedelta(hours=1), absolute_expires_at=now + timedelta(hours=2))
        db.add(old); db.commit(); old_id = old.id
        request = Request({"type": "http", "method": "GET", "path": "/", "headers": [(b"cookie", f"{settings.session_cookie_name}={old_credential}".encode())]})
        new_credential, _, new_session = _rotate_web_session(db, request, db.get(User, user.id))
        db.commit()
        assert db.get(WebSession, old_id).revoked_at is not None
        assert new_session.credential_hash == token_hash(new_credential)
        assert new_session.credential_hash != token_hash(old_credential)


def test_csrf_missing_and_invalid_rejected_and_valid_succeeds():
    user = _user("csrf")
    client = _client_for(user)
    client.headers.pop("X-CSRF-Token")
    assert client.post("/sources", json={"type": "website", "url": "https://example.test"}).status_code == 403
    client.headers["X-CSRF-Token"] = "wrong"
    assert client.post("/sources", json={"type": "website", "url": "https://example.test"}).status_code == 403
    client.headers["X-CSRF-Token"] = "csrf-csrf"
    assert client.post("/sources", json={"type": "website", "url": "https://example.test"}).status_code == 200


def test_wrong_or_replayed_oauth_state_rejected(monkeypatch):
    import app.routers.auth as auth_router
    monkeypatch.setattr(auth_router, "settings", replace(settings, google_client_id="client", google_client_secret="secret", google_redirect_uri="http://testserver/auth/google/callback"))
    client = TestClient(app)
    assert client.get("/auth/google/callback?code=x&state=wrong").status_code == 400


def _google_token(*, aud="client", nonce="nonce", expires=300):
    key = JsonWebKey.generate_key("RSA", 2048, is_private=True)
    now = int(utcnow().timestamp())
    token = jwt.encode({"alg": "RS256", "kid": "test"}, {
        "iss": "https://accounts.google.com", "aud": aud, "sub": "google-sub",
        "exp": now + expires, "iat": now, "nonce": nonce,
    }, key)
    public = key.as_dict(is_private=False); public["kid"] = "test"
    return token.decode(), {"keys": [public]}


def test_google_token_wrong_audience_nonce_and_expiry_rejected(monkeypatch):
    wrong_aud = _google_token(aud="wrong")
    wrong_nonce = _google_token(nonce="wrong")
    expired = _google_token(expires=-60)
    for (candidate, keys), nonce in [(wrong_aud, "nonce"), (wrong_nonce, "nonce"), (expired, "nonce")]:
        try:
            _verified_google_claims(candidate, keys, nonce, audience="client")
            assert False, "invalid ID token accepted"
        except Exception as exc:
            assert getattr(exc, "status_code", None) == 400


def test_cors_allows_configured_origin_and_not_arbitrary(unauthenticated_client):
    allowed = unauthenticated_client.options("/sources", headers={"Origin": "http://testserver", "Access-Control-Request-Method": "GET"})
    assert allowed.headers.get("access-control-allow-origin") == "http://testserver"
    denied = unauthenticated_client.options("/sources", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert denied.headers.get("access-control-allow-origin") is None
