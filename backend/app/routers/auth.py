import hmac
from datetime import timedelta
from urllib.parse import urlencode

import httpx
from authlib.jose import JsonWebToken, JoseError
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth_dependencies import get_current_session, get_current_user, require_csrf
from app.config import settings
from app.database import get_db
from app.models.auth import LegacyClaim, OAuthTransaction, User, WebSession
from app.models.source import Source
from app.schemas.auth import AuthResponse, UserResponse
from app.security import pkce_challenge, random_token, token_hash, utcnow

router = APIRouter(prefix="/auth")
GOOGLE_AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_ENDPOINT = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = {"https://accounts.google.com", "accounts.google.com"}


def _require_google_config() -> None:
    if not settings.google_client_id or not settings.google_client_secret or not settings.google_redirect_uri:
        raise HTTPException(status_code=503, detail="Google authentication is not configured")


def _safe_return_to(value: str) -> str:
    return value if value.startswith("/") and not value.startswith("//") else "/app"


def _web_redirect(path: str) -> str:
    web_origins = [origin for origin in settings.web_origins if origin.startswith(("http://", "https://"))]
    if not web_origins:
        raise HTTPException(status_code=503, detail="Web origin is not configured")
    return f"{web_origins[0]}{_safe_return_to(path)}"


def _set_auth_cookies(response: Response, credential: str, csrf: str) -> None:
    common = dict(secure=settings.cookie_secure, samesite="lax", path="/")
    response.set_cookie(settings.session_cookie_name, credential, httponly=True, max_age=settings.session_absolute_seconds, **common)
    response.set_cookie("lucent_csrf", csrf, httponly=False, max_age=settings.session_absolute_seconds, **common)


def _new_session(db: Session, user: User) -> tuple[str, str, WebSession]:
    credential, csrf = random_token(32), random_token(32)
    now = utcnow()
    row = WebSession(
        user_id=user.id,
        credential_hash=token_hash(credential),
        csrf_hash=token_hash(csrf),
        idle_expires_at=now + timedelta(seconds=settings.session_idle_seconds),
        absolute_expires_at=now + timedelta(seconds=settings.session_absolute_seconds),
    )
    db.add(row)
    db.flush()
    return credential, csrf, row


def _claim_legacy_once(db: Session, user: User) -> None:
    if not settings.enable_legacy_claim or settings.environment != "development" or user.provider != "google":
        return
    existing_claim = db.get(LegacyClaim, 1)
    if existing_claim:
        if existing_claim.user_id != user.id:
            raise HTTPException(status_code=409, detail="Legacy data was already claimed")
        return
    unowned = db.execute(select(Source).where(Source.user_id.is_(None)).with_for_update()).scalars().all()
    if unowned:
        for source in unowned:
            source.user_id = user.id
    db.add(LegacyClaim(id=1, user_id=user.id))
    db.flush()


@router.get("/google/start")
def google_start(return_to: str = Query("/app"), db: Session = Depends(get_db)):
    _require_google_config()
    state, verifier, nonce = random_token(), random_token(48), random_token()
    db.add(OAuthTransaction(
        state_hash=token_hash(state), code_verifier=verifier, nonce=nonce,
        return_to=_safe_return_to(return_to), expires_at=utcnow() + timedelta(minutes=10),
    ))
    db.commit()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": pkce_challenge(verifier),
        "code_challenge_method": "S256",
    }
    return RedirectResponse(f"{GOOGLE_AUTHORIZATION_ENDPOINT}?{urlencode(params)}", status_code=302)


def _verified_google_claims(id_token: str, jwks: dict, nonce: str, audience: str | None = None) -> dict:
    expected_audience = audience or settings.google_client_id
    try:
        claims = JsonWebToken(["RS256"]).decode(
            id_token,
            jwks,
            claims_options={
                "iss": {"essential": True, "values": list(GOOGLE_ISSUERS)},
                "aud": {"essential": True, "value": expected_audience},
                "exp": {"essential": True},
                "sub": {"essential": True},
                "nonce": {"essential": True, "value": nonce},
            },
        )
        claims.validate(leeway=30)
    except JoseError as exc:
        raise HTTPException(status_code=400, detail="Google identity validation failed") from exc
    if claims.get("nonce") != nonce or claims.get("iss") not in GOOGLE_ISSUERS or claims.get("aud") != expected_audience:
        raise HTTPException(status_code=400, detail="Google identity validation failed")
    return dict(claims)


@router.get("/google/callback")
def google_callback(request: Request, code: str, state: str, db: Session = Depends(get_db)):
    _require_google_config()
    transaction = db.execute(
        select(OAuthTransaction).where(OAuthTransaction.state_hash == token_hash(state)).with_for_update()
    ).scalar_one_or_none()
    now = utcnow()
    if not transaction or transaction.used_at or transaction.expires_at <= now:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    transaction.used_at = now
    with httpx.Client(timeout=10) as client:
        token_response = client.post(GOOGLE_TOKEN_ENDPOINT, data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": transaction.code_verifier,
        })
        if token_response.status_code != 200:
            db.commit()
            raise HTTPException(status_code=400, detail="Google authorization failed")
        id_token = token_response.json().get("id_token")
        if not id_token:
            raise HTTPException(status_code=400, detail="Google identity token missing")
        jwks_response = client.get(GOOGLE_JWKS_ENDPOINT)
        jwks_response.raise_for_status()
    claims = _verified_google_claims(id_token, jwks_response.json(), transaction.nonce)
    user = db.execute(select(User).where(User.provider == "google", User.provider_subject == claims["sub"])).scalar_one_or_none()
    if not user:
        user = User(provider="google", provider_subject=claims["sub"])
        db.add(user)
        db.flush()
    user.email = claims.get("email")
    user.email_verified = bool(claims.get("email_verified"))
    user.display_name = claims.get("name")
    user.avatar_url = claims.get("picture")
    user.last_login_at = now
    _claim_legacy_once(db, user)
    credential, csrf, _ = _new_session(db, user)
    db.commit()
    response = RedirectResponse(_web_redirect(transaction.return_to), status_code=303)
    _set_auth_cookies(response, credential, csrf)
    return response


@router.get("/me", response_model=AuthResponse)
def me(request: Request, user: User = Depends(get_current_user)):
    csrf = request.cookies.get("lucent_csrf")
    if not csrf:
        raise HTTPException(status_code=401, detail="Authentication required")
    return AuthResponse(user=UserResponse.model_validate(user), csrf_token=csrf)


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf)])
def logout(response: Response, session: WebSession = Depends(get_current_session), db: Session = Depends(get_db)):
    session.revoked_at = utcnow()
    db.commit()
    response.delete_cookie(settings.session_cookie_name, path="/", secure=settings.cookie_secure, httponly=True, samesite="lax")
    response.delete_cookie("lucent_csrf", path="/", secure=settings.cookie_secure, samesite="lax")


@router.post("/development-login", response_model=AuthResponse)
def development_login(response: Response, request: Request, db: Session = Depends(get_db)):
    if settings.environment != "development" or not settings.enable_development_auth:
        raise HTTPException(status_code=404, detail="Not found")
    origin = request.headers.get("origin")
    if not origin or origin.rstrip("/") not in settings.web_origins:
        raise HTTPException(status_code=403, detail="Request origin rejected")
    user = db.execute(select(User).where(User.provider == "development", User.provider_subject == "local-development-user")).scalar_one_or_none()
    if not user:
        user = User(provider="development", provider_subject="local-development-user", email="dev@lucent.local", email_verified=True, display_name="Development User")
        db.add(user)
        db.flush()
    credential, csrf, _ = _new_session(db, user)
    db.commit()
    _set_auth_cookies(response, credential, csrf)
    return AuthResponse(user=UserResponse.model_validate(user), csrf_token=csrf)
