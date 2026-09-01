import hmac
from datetime import timedelta
from urllib.parse import urlencode

import httpx
from authlib.jose import JsonWebToken, JoseError
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth_dependencies import _active_cookie_session, get_current_session, get_current_user, require_csrf
from app.config import settings
from app.database import get_db
from app.models.auth import ExtensionAccessToken, ExtensionAuthorizationCode, ExtensionGrant, ExtensionRefreshToken, LegacyClaim, OAuthTransaction, User, WebSession
from app.models.source import Source
from app.schemas.auth import AuthResponse, ExtensionRefreshRequest, ExtensionTokenExchange, ExtensionTokenResponse, UserResponse
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


def _extension_redirect_allowed(uri: str) -> bool:
    return any(uri == f"https://{extension_id}.chromiumapp.org/lucent-auth" for extension_id in settings.extension_ids)


def _issue_extension_code(db: Session, user: User, challenge: str, redirect_uri: str) -> str:
    code = random_token(32)
    db.add(ExtensionAuthorizationCode(
        user_id=user.id, code_hash=token_hash(code), code_challenge=challenge,
        redirect_uri=redirect_uri, expires_at=utcnow() + timedelta(minutes=2),
    ))
    db.flush()
    return code


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


@router.get("/extension/start")
def extension_start(
    request: Request,
    state: str,
    code_challenge: str,
    redirect_uri: str,
    db: Session = Depends(get_db),
):
    _require_google_config()
    if not _extension_redirect_allowed(redirect_uri) or len(state) < 32 or len(code_challenge) != 43:
        raise HTTPException(status_code=400, detail="Invalid extension authorization request")
    state_token, verifier, nonce = random_token(), random_token(48), random_token()
    db.add(OAuthTransaction(
        state_hash=token_hash(state_token), code_verifier=verifier, nonce=nonce,
        flow_type="extension", return_to="/app", extension_state=state,
        extension_redirect_uri=redirect_uri, extension_code_challenge=code_challenge,
        expires_at=utcnow() + timedelta(minutes=10),
    ))
    db.commit()
    params = {
        "client_id": settings.google_client_id, "redirect_uri": settings.google_redirect_uri,
        "response_type": "code", "scope": "openid email profile", "state": state_token,
        "nonce": nonce, "code_challenge": pkce_challenge(verifier), "code_challenge_method": "S256",
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
    audience = claims.get("aud")
    audience_valid = expected_audience in audience if isinstance(audience, list) else audience == expected_audience
    authorized_party_valid = not isinstance(audience, list) or claims.get("azp") == expected_audience
    if claims.get("nonce") != nonce or claims.get("iss") not in GOOGLE_ISSUERS or not audience_valid or not authorized_party_valid:
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
    if transaction.flow_type == "extension":
        if not transaction.extension_redirect_uri or not transaction.extension_code_challenge or not transaction.extension_state:
            raise HTTPException(status_code=400, detail="Invalid extension authorization transaction")
        extension_code = _issue_extension_code(db, user, transaction.extension_code_challenge, transaction.extension_redirect_uri)
        db.commit()
        query = urlencode({"code": extension_code, "state": transaction.extension_state})
        return RedirectResponse(f"{transaction.extension_redirect_uri}?{query}", status_code=303)
    prior_session = _active_cookie_session(request, db)
    if prior_session:
        prior_session.revoked_at = now
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


def _new_extension_tokens(db: Session, grant: ExtensionGrant) -> tuple[str, str]:
    access, refresh = random_token(32), random_token(48)
    now = utcnow()
    db.add(ExtensionAccessToken(grant_id=grant.id, token_hash=token_hash(access), expires_at=now + timedelta(minutes=15)))
    db.add(ExtensionRefreshToken(grant_id=grant.id, token_hash=token_hash(refresh), expires_at=now + timedelta(days=30)))
    return access, refresh


@router.post("/extension/token", response_model=ExtensionTokenResponse)
def extension_token(payload: ExtensionTokenExchange, db: Session = Depends(get_db)):
    row = db.execute(
        select(ExtensionAuthorizationCode).where(ExtensionAuthorizationCode.code_hash == token_hash(payload.code)).with_for_update()
    ).scalar_one_or_none()
    now = utcnow()
    if not row or row.used_at or row.expires_at <= now or not _extension_redirect_allowed(payload.redirect_uri):
        raise HTTPException(status_code=400, detail="Invalid or expired authorization code")
    if row.redirect_uri != payload.redirect_uri or not hmac.compare_digest(pkce_challenge(payload.code_verifier), row.code_challenge):
        raise HTTPException(status_code=400, detail="PKCE verification failed")
    row.used_at = now
    grant = ExtensionGrant(user_id=row.user_id)
    db.add(grant); db.flush()
    access, refresh = _new_extension_tokens(db, grant)
    db.commit()
    return ExtensionTokenResponse(access_token=access, refresh_token=refresh)


def _revoke_grant(db: Session, grant: ExtensionGrant) -> None:
    now = utcnow(); grant.revoked_at = now
    db.execute(update(ExtensionAccessToken).where(ExtensionAccessToken.grant_id == grant.id, ExtensionAccessToken.revoked_at.is_(None)).values(revoked_at=now))
    db.execute(update(ExtensionRefreshToken).where(ExtensionRefreshToken.grant_id == grant.id, ExtensionRefreshToken.revoked_at.is_(None)).values(revoked_at=now))


@router.post("/extension/refresh", response_model=ExtensionTokenResponse)
def extension_refresh(payload: ExtensionRefreshRequest, db: Session = Depends(get_db)):
    row = db.execute(
        select(ExtensionRefreshToken).where(ExtensionRefreshToken.token_hash == token_hash(payload.refresh_token)).with_for_update()
    ).scalar_one_or_none()
    now = utcnow()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    grant = db.execute(select(ExtensionGrant).where(ExtensionGrant.id == row.grant_id).with_for_update()).scalar_one()
    if row.used_at or row.revoked_at:
        _revoke_grant(db, grant); db.commit()
        raise HTTPException(status_code=401, detail="Refresh token reuse detected; device access revoked")
    if row.expires_at <= now or grant.revoked_at:
        raise HTTPException(status_code=401, detail="Refresh token expired or revoked")
    row.used_at = now
    access, refresh = _new_extension_tokens(db, grant)
    db.flush()
    replacement = db.execute(select(ExtensionRefreshToken).where(ExtensionRefreshToken.token_hash == token_hash(refresh))).scalar_one()
    row.replaced_by_id = replacement.id
    grant.last_seen_at = now
    db.commit()
    return ExtensionTokenResponse(access_token=access, refresh_token=refresh)


@router.get("/extension/me", response_model=UserResponse)
def extension_me(user: User = Depends(get_current_user)):
    return user


@router.post("/extension/logout", status_code=204)
def extension_logout(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    credential = request.headers.get("authorization", "").partition(" ")[2]
    token = db.execute(select(ExtensionAccessToken).where(ExtensionAccessToken.token_hash == token_hash(credential))).scalar_one_or_none()
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    grant = db.get(ExtensionGrant, token.grant_id)
    if not grant or grant.user_id != user.id:
        raise HTTPException(status_code=401, detail="Authentication required")
    _revoke_grant(db, grant); db.commit()
