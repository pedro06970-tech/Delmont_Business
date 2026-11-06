from datetime import UTC, datetime
from ipaddress import ip_address

from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_session, get_current_user, require_csrf
from app.core.config import settings
from app.core.errors import AppError
from app.core.security import cookie_secure, hash_password, verify_password
from app.db.session import get_db
from app.models.auth import AuthSession
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, MessageResponse
from app.schemas.user import UserResponse
from app.services.auth import (
    authenticate,
    create_session,
    login_is_limited,
    revoke_user_sessions,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


def request_ip(request: Request) -> str:
    host = request.client.host if request.client else "127.0.0.1"
    try:
        return str(ip_address(host))
    except ValueError:
        return "127.0.0.1"


def set_auth_cookies(response: Response, session_token: str, csrf_token: str) -> None:
    max_age = settings.SESSION_TTL_MINUTES * 60
    response.set_cookie(
        settings.SESSION_COOKIE_NAME,
        session_token,
        max_age=max_age,
        httponly=True,
        secure=cookie_secure(),
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        settings.CSRF_COOKIE_NAME,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=cookie_secure(),
        samesite="lax",
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(settings.SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(settings.CSRF_COOKIE_NAME, path="/")


@router.post("/login", response_model=UserResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    client_ip = request_ip(request)
    if login_is_limited(db, str(payload.email), client_ip):
        raise AppError(429, "too_many_attempts", "Muitas tentativas. Tente novamente mais tarde.")

    user = authenticate(db, str(payload.email), payload.password, client_ip)
    if not user:
        raise AppError(401, "invalid_credentials", "E-mail ou senha inválidos.")

    _session, session_token, csrf_token = create_session(db, user)
    set_auth_cookies(response, session_token, csrf_token)
    return user


@router.post("/logout", response_model=MessageResponse)
def logout(
    response: Response,
    auth_session: AuthSession = Depends(get_current_session),
    _user: User = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> MessageResponse:
    auth_session.revoked_at = datetime.now(UTC)
    db.commit()
    clear_auth_cookies(response)
    return MessageResponse(message="Sessão encerrada.")


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    user: User = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> MessageResponse:
    if not verify_password(payload.current_password, user.password_hash):
        raise AppError(400, "invalid_current_password", "A senha atual está incorreta.")
    if verify_password(payload.new_password, user.password_hash):
        raise AppError(400, "password_reused", "A nova senha deve ser diferente da atual.")

    user.password_hash = hash_password(payload.new_password)
    db.commit()
    revoke_user_sessions(db, user.id)
    clear_auth_cookies(response)
    return MessageResponse(message="Senha alterada. Entre novamente.")
