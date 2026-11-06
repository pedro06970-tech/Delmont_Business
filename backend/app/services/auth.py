from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    generate_token,
    hash_token,
    session_expiration,
    verify_password,
)
from app.models.auth import AuthSession, LoginAttempt
from app.models.user import User


def login_is_limited(db: Session, email: str, ip_address: str) -> bool:
    since = datetime.now(UTC) - timedelta(minutes=settings.LOGIN_WINDOW_MINUTES)
    attempts = db.scalar(
        select(func.count(LoginAttempt.id)).where(
            LoginAttempt.email == email,
            LoginAttempt.ip_address == ip_address,
            LoginAttempt.attempted_at >= since,
        )
    )
    return bool(attempts and attempts >= settings.LOGIN_MAX_ATTEMPTS)


def authenticate(db: Session, email: str, password: str, ip_address: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email))
    password_valid = verify_password(password, user.password_hash if user else DUMMY_PASSWORD_HASH)

    if not user or not password_valid or not user.is_active:
        db.add(LoginAttempt(email=email, ip_address=ip_address))
        db.commit()
        return None

    db.execute(
        delete(LoginAttempt).where(
            LoginAttempt.email == email, LoginAttempt.ip_address == ip_address
        )
    )
    db.commit()
    return user


def create_session(db: Session, user: User) -> tuple[AuthSession, str, str]:
    session_token = generate_token()
    csrf_token = generate_token()
    session = AuthSession(
        user_id=user.id,
        token_hash=hash_token(session_token),
        csrf_hash=hash_token(csrf_token),
        expires_at=session_expiration(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session, session_token, csrf_token


def revoke_user_sessions(db: Session, user_id) -> None:
    db.query(AuthSession).filter(
        AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)
    ).update({AuthSession.revoked_at: datetime.now(UTC)}, synchronize_session=False)
    db.commit()
