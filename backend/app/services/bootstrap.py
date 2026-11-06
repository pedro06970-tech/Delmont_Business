from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.schemas.auth import normalize_email


def bootstrap_admin(
    db: Session, *, name: str, email: str, password: str
) -> tuple[User, bool]:
    normalized_email = normalize_email(email)
    existing = db.scalar(select(User).where(User.email == normalized_email))
    if existing:
        if existing.role != UserRole.ADMIN:
            raise AppError(
                409,
                "email_in_use",
                "O e-mail já pertence a um usuário que não é administrador.",
            )
        return existing, False

    if len(password) < 12 or len(password) > 128:
        raise AppError(422, "invalid_password", "A senha deve ter entre 12 e 128 caracteres.")
    clean_name = name.strip()
    if len(clean_name) < 2:
        raise AppError(422, "invalid_name", "Informe o nome do administrador.")

    user = User(
        name=clean_name,
        email=normalized_email,
        password_hash=hash_password(password),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, True
