from dataclasses import replace
from datetime import timedelta

from fastapi.testclient import TestClient

import app.routers.auth as auth_router
from app.config import settings
from app.main import app
from app.models.auth import ExtensionAccessToken, ExtensionAuthorizationCode
from app.security import pkce_challenge, token_hash, utcnow
from conftest import TestSessionLocal
from test_auth_security import _user

REDIRECT = "https://testextension.chromiumapp.org/lucent-auth"
VERIFIER = "v" * 64
STATE = "s" * 48


def _authorization_code(user, code="one-time-code"):
    with TestSessionLocal() as db:
        db.add(ExtensionAuthorizationCode(
            user_id=user.id, code_hash=token_hash(code), state_hash=token_hash(STATE), code_challenge=pkce_challenge(VERIFIER),
            redirect_uri=REDIRECT, expires_at=utcnow() + timedelta(minutes=2),
        )); db.commit()
    return code


def _configured(monkeypatch):
    monkeypatch.setattr(auth_router, "settings", replace(settings, extension_ids=("testextension",)))


def test_authorization_code_pkce_and_single_use(monkeypatch):
    _configured(monkeypatch)
    code = _authorization_code(_user("extension-code"))
    client = TestClient(app)
    assert client.post("/auth/extension/token", json={"code": code, "state": "wrong", "code_verifier": VERIFIER, "redirect_uri": REDIRECT}).status_code == 400
    wrong = client.post("/auth/extension/token", json={"code": code, "state": STATE, "code_verifier": "wrong", "redirect_uri": REDIRECT})
    assert wrong.status_code == 400
    good = client.post("/auth/extension/token", json={"code": code, "state": STATE, "code_verifier": VERIFIER, "redirect_uri": REDIRECT})
    assert good.status_code == 200
    assert client.post("/auth/extension/token", json={"code": code, "state": STATE, "code_verifier": VERIFIER, "redirect_uri": REDIRECT}).status_code == 400


def test_access_expiry_refresh_rotation_and_reuse_revokes_family(monkeypatch):
    _configured(monkeypatch)
    code = _authorization_code(_user("extension-refresh"), "refresh-code")
    client = TestClient(app)
    issued = client.post("/auth/extension/token", json={"code": code, "state": STATE, "code_verifier": VERIFIER, "redirect_uri": REDIRECT}).json()
    assert client.get("/sources", headers={"Authorization": f"Bearer {issued['access_token']}"}).status_code == 200
    rotated = client.post("/auth/extension/refresh", json={"refresh_token": issued["refresh_token"]})
    assert rotated.status_code == 200
    new_tokens = rotated.json()
    reuse = client.post("/auth/extension/refresh", json={"refresh_token": issued["refresh_token"]})
    assert reuse.status_code == 401
    assert client.get("/sources", headers={"Authorization": f"Bearer {new_tokens['access_token']}"}).status_code == 401


def test_expired_access_and_revoked_grant_rejected(monkeypatch):
    _configured(monkeypatch)
    code = _authorization_code(_user("extension-expired"), "expired-code")
    client = TestClient(app)
    issued = client.post("/auth/extension/token", json={"code": code, "state": STATE, "code_verifier": VERIFIER, "redirect_uri": REDIRECT}).json()
    with TestSessionLocal() as db:
        token = db.query(ExtensionAccessToken).filter_by(token_hash=token_hash(issued["access_token"])).one()
        token.expires_at = utcnow() - timedelta(seconds=1); db.commit()
    assert client.get("/sources", headers={"Authorization": f"Bearer {issued['access_token']}"}).status_code == 401


def test_extension_start_rejects_invalid_state_and_redirect(monkeypatch):
    configured = replace(settings, extension_ids=("testextension",), google_client_id="client", google_client_secret="secret", google_redirect_uri="http://testserver/auth/google/callback")
    monkeypatch.setattr(auth_router, "settings", configured)
    client = TestClient(app)
    response = client.get("/auth/extension/start", params={"state": "short", "code_challenge": "x" * 43, "redirect_uri": REDIRECT})
    assert response.status_code == 400
    response = client.get("/auth/extension/start", params={"state": "x" * 32, "code_challenge": "x" * 43, "redirect_uri": "https://evil.example/callback"})
    assert response.status_code == 400
