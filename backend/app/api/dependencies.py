import secrets
from datetime import UTC, datetime

from fastapi import Cookie, Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import hash_token
from app.db.session import get_db
from app.models.auth import AuthSession
from app.models.user import User, UserRole


def get_current_session(
    session_token: str | None = Cookie(default=None, alias=settings.SESSION_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> AuthSession:
    if not session_token:
        raise AppError(401, "not_authenticated", "Autenticação necessária.")

    auth_session = db.scalar(
        select(AuthSession)
        .options(joinedload(AuthSession.user))
        .where(AuthSession.token_hash == hash_token(session_token))
    )
    now = datetime.now(UTC)
    if (
        not auth_session
        or auth_session.revoked_at is not None
        or auth_session.expires_at <= now
        or not auth_session.user.is_active
    ):
        raise AppError(401, "invalid_session", "Sessão inválida ou expirada.")
    return auth_session


def get_current_user(auth_session: AuthSession = Depends(get_current_session)) -> User:
    return auth_session.user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise AppError(403, "admin_required", "Acesso restrito a administradores.")
    return user


def require_csrf(
    auth_session: AuthSession = Depends(get_current_session),
    csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> User:
    if not csrf_token or not secrets.compare_digest(
        hash_token(csrf_token), auth_session.csrf_hash
    ):
        raise AppError(403, "invalid_csrf", "Token CSRF inválido.")
    return auth_session.user


def require_admin_csrf(user: User = Depends(require_csrf)) -> User:
    if user.role != UserRole.ADMIN:
        raise AppError(403, "admin_required", "Acesso restrito a administradores.")
    return user
