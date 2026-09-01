import hmac
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.auth import ExtensionAccessToken, ExtensionGrant, User, WebSession
from app.security import token_hash, utcnow


AUTHENTICATION_REQUIRED = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


def _active_cookie_session(request: Request, db: Session) -> WebSession | None:
    credential = request.cookies.get(settings.session_cookie_name)
    if not credential:
        return None
    session = db.execute(
        select(WebSession).where(WebSession.credential_hash == token_hash(credential))
    ).scalar_one_or_none()
    now = utcnow()
    if not session or session.revoked_at or session.idle_expires_at <= now or session.absolute_expires_at <= now:
        return None
    session.last_seen_at = now
    session.idle_expires_at = min(now + timedelta(seconds=settings.session_idle_seconds), session.absolute_expires_at)
    db.commit()
    return session


def get_current_session(request: Request, db: Session = Depends(get_db)) -> WebSession:
    session = _active_cookie_session(request, db)
    if not session:
        raise AUTHENTICATION_REQUIRED
    return session


def _bearer_user(request: Request, db: Session) -> User | None:
    authorization = request.headers.get("authorization", "")
    scheme, _, credential = authorization.partition(" ")
    if scheme.lower() != "bearer" or not credential:
        return None
    now = utcnow()
    row = db.execute(
        select(ExtensionAccessToken, ExtensionGrant)
        .join(ExtensionGrant, ExtensionGrant.id == ExtensionAccessToken.grant_id)
        .where(
            ExtensionAccessToken.token_hash == token_hash(credential),
            ExtensionAccessToken.expires_at > now,
            ExtensionAccessToken.revoked_at.is_(None),
            ExtensionGrant.revoked_at.is_(None),
        )
    ).one_or_none()
    if not row:
        return None
    token, grant = row
    grant.last_seen_at = now
    db.commit()
    return db.get(User, grant.user_id)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    session = _active_cookie_session(request, db)
    user = db.get(User, session.user_id) if session else _bearer_user(request, db)
    if not user or user.status != "active":
        raise AUTHENTICATION_REQUIRED
    return user


def require_csrf(
    request: Request,
    db: Session = Depends(get_db),
) -> None:
    if request.headers.get("authorization", "").lower().startswith("bearer "):
        if not _bearer_user(request, db):
            raise AUTHENTICATION_REQUIRED
        return
    session = _active_cookie_session(request, db)
    if not session:
        raise AUTHENTICATION_REQUIRED
    origin = request.headers.get("origin")
    if not origin or origin.rstrip("/") not in settings.web_origins:
        raise HTTPException(status_code=403, detail="Request origin rejected")
    cookie_token = request.cookies.get("lucent_csrf")
    header_token = request.headers.get("x-csrf-token")
    if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=403, detail="CSRF validation failed")
    if not hmac.compare_digest(token_hash(cookie_token), session.csrf_hash):
        raise HTTPException(status_code=403, detail="CSRF validation failed")
