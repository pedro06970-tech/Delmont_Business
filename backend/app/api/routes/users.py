import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin, require_admin_csrf
from app.core.errors import AppError
from app.core.security import hash_password
from app.db.session import get_db
from app.models.store import Store, UserStore
from app.models.user import User, UserRole
from app.schemas.store import StoreResponse, UserStoreUpdate, UserStoresResponse
from app.schemas.user import UserCreate, UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


def get_user_or_404(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if not user:
        raise AppError(404, "user_not_found", "Usuário não encontrado.")
    return user


@router.get("", response_model=list[UserResponse])
def list_users(
    _admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.name)))


@router.post("", response_model=UserResponse, status_code=201)
def create_user(
    payload: UserCreate,
    _admin: User = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
) -> User:
    user = User(
        name=payload.name,
        email=str(payload.email),
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=payload.is_active,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "email_already_exists", "Já existe um usuário com este e-mail.")
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    _admin: User = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
) -> User:
    user = get_user_or_404(db, user_id)
    updates = payload.model_dump(exclude_unset=True)
    removing_active_admin = (
        user.role == UserRole.ADMIN
        and user.is_active
        and (
            updates.get("role", UserRole.ADMIN) != UserRole.ADMIN
            or updates.get("is_active", True) is False
        )
    )
    if removing_active_admin:
        other_admins = db.scalar(
            select(func.count(User.id)).where(
                User.role == UserRole.ADMIN,
                User.is_active.is_(True),
                User.id != user.id,
            )
        )
        if not other_admins:
            raise AppError(
                409,
                "last_active_admin",
                "O sistema deve manter pelo menos um administrador ativo.",
            )

    for field, value in updates.items():
        if field == "email" and value is not None:
            value = str(value)
        setattr(user, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "email_already_exists", "Já existe um usuário com este e-mail.")
    db.refresh(user)
    return user


@router.get("/{user_id}/stores", response_model=UserStoresResponse)
def get_user_stores(
    user_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserStoresResponse:
    get_user_or_404(db, user_id)
    stores = list(
        db.scalars(
            select(Store)
            .join(UserStore, UserStore.store_id == Store.id)
            .where(UserStore.user_id == user_id)
            .order_by(Store.name)
        )
    )
    return UserStoresResponse(user_id=user_id, stores=[StoreResponse.model_validate(s) for s in stores])


@router.put("/{user_id}/stores", response_model=UserStoresResponse)
def replace_user_stores(
    user_id: uuid.UUID,
    payload: UserStoreUpdate,
    _admin: User = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
) -> UserStoresResponse:
    get_user_or_404(db, user_id)
    requested_ids = set(payload.store_ids)
    stores = list(db.scalars(select(Store).where(Store.id.in_(requested_ids)))) if requested_ids else []
    if len(stores) != len(requested_ids):
        raise AppError(400, "invalid_store", "Uma ou mais lojas não existem.")

    db.query(UserStore).filter(UserStore.user_id == user_id).delete()
    db.add_all(UserStore(user_id=user_id, store_id=store_id) for store_id in requested_ids)
    db.commit()
    stores.sort(key=lambda store: store.name)
    return UserStoresResponse(user_id=user_id, stores=[StoreResponse.model_validate(s) for s in stores])
