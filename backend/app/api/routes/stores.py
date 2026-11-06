import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin_csrf
from app.core.errors import AppError
from app.db.session import get_db
from app.models.store import Store, UserStore
from app.models.user import User, UserRole
from app.schemas.store import StoreCreate, StoreResponse, StoreUpdate

router = APIRouter(prefix="/stores", tags=["stores"])


def visible_store_query(user: User):
    query = select(Store)
    if user.role == UserRole.COLLABORATOR:
        query = query.join(UserStore, UserStore.store_id == Store.id).where(
            UserStore.user_id == user.id, Store.is_active.is_(True)
        )
    return query


@router.get("", response_model=list[StoreResponse])
def list_stores(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Store]:
    return list(db.scalars(visible_store_query(user).order_by(Store.name)))


@router.get("/{store_id}", response_model=StoreResponse)
def get_store(
    store_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Store:
    store = db.scalar(visible_store_query(user).where(Store.id == store_id))
    if not store:
        raise AppError(404, "store_not_found", "Loja não encontrada ou não autorizada.")
    if not store.is_active:
        raise AppError(409, "inactive_store", "Esta loja está inativa.")
    return store


@router.post("", response_model=StoreResponse, status_code=201)
def create_store(
    payload: StoreCreate,
    _admin: User = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
) -> Store:
    store = Store(name=payload.name, is_active=payload.is_active)
    db.add(store)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "store_already_exists", "Já existe uma loja com este nome.")
    db.refresh(store)
    return store


@router.patch("/{store_id}", response_model=StoreResponse)
def update_store(
    store_id: uuid.UUID,
    payload: StoreUpdate,
    _admin: User = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
) -> Store:
    store = db.get(Store, store_id)
    if not store:
        raise AppError(404, "store_not_found", "Loja não encontrada.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(store, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "store_already_exists", "Já existe uma loja com este nome.")
    db.refresh(store)
    return store
