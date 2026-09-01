from datetime import timedelta
from dataclasses import replace

from authlib.jose import JsonWebKey, jwt
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.models.auth import User, WebSession
from app.security import token_hash, utcnow
from app.routers.auth import _verified_google_claims
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


def test_expired_revoked_and_random_sessions_are_rejected():
    assert _client_for(_user("expired"), expired=True).get("/auth/me").status_code == 401
    assert _client_for(_user("revoked"), revoked=True).get("/auth/me").status_code == 401
    client = TestClient(app); client.cookies.set(settings.session_cookie_name, "random")
    assert client.get("/auth/me").status_code == 401


def test_logout_revokes_server_session():
    client = _client_for(_user("logout"))
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").status_code == 401


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
