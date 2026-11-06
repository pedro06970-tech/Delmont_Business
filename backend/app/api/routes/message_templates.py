import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_operational_store, require_csrf
from app.core.errors import AppError
from app.db.session import get_db
from app.models.commercial import MessageTemplate
from app.models.store import UserStore
from app.models.user import User, UserRole
from app.schemas.commercial import (
    MessagePreviewRequest,
    MessagePreviewResponse,
    MessageTemplateCreate,
    MessageTemplateResponse,
    MessageTemplateUpdate,
)
from app.services.commercial import render_template, validate_template_content

router = APIRouter(prefix="/message-templates", tags=["message templates"])


def get_template_for_user(
    db: Session, user: User, template_id: uuid.UUID
) -> MessageTemplate:
    query = select(MessageTemplate).where(MessageTemplate.id == template_id)
    if user.role == UserRole.COLLABORATOR:
        query = query.join(
            UserStore, UserStore.store_id == MessageTemplate.store_id
        ).where(UserStore.user_id == user.id)
    template = db.scalar(query)
    if not template:
        raise AppError(404, "template_not_found", "Modelo não encontrado ou não autorizado.")
    get_operational_store(db, user, template.store_id)
    return template


@router.get("", response_model=list[MessageTemplateResponse])
def list_templates(
    store_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MessageTemplate]:
    get_operational_store(db, user, store_id)
    return list(
        db.scalars(
            select(MessageTemplate)
            .where(MessageTemplate.store_id == store_id)
            .order_by(MessageTemplate.name)
        )
    )


@router.post("", response_model=MessageTemplateResponse, status_code=201)
def create_template(
    payload: MessageTemplateCreate,
    user: User = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> MessageTemplate:
    get_operational_store(db, user, payload.store_id)
    template = MessageTemplate(
        store_id=payload.store_id,
        name=payload.name,
        content=validate_template_content(payload.content),
        is_active=payload.is_active,
        created_by_user_id=user.id,
    )
    db.add(template)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "template_name_exists", "Já existe um modelo com este nome na loja.")
    db.refresh(template)
    return template


@router.get("/{template_id}", response_model=MessageTemplateResponse)
def get_template(
    template_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageTemplate:
    return get_template_for_user(db, user, template_id)


@router.patch("/{template_id}", response_model=MessageTemplateResponse)
def update_template(
    template_id: uuid.UUID,
    payload: MessageTemplateUpdate,
    user: User = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> MessageTemplate:
    template = get_template_for_user(db, user, template_id)
    updates = payload.model_dump(exclude_unset=True)
    if "content" in updates:
        updates["content"] = validate_template_content(updates["content"])
    for field, value in updates.items():
        setattr(template, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "template_name_exists", "Já existe um modelo com este nome na loja.")
    db.refresh(template)
    return template


@router.post("/{template_id}/preview", response_model=MessagePreviewResponse)
def preview_template(
    template_id: uuid.UUID,
    payload: MessagePreviewRequest,
    user: User = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> MessagePreviewResponse:
    template = get_template_for_user(db, user, template_id)
    if not template.is_active:
        raise AppError(409, "inactive_template", "Modelos inativos não podem ser utilizados.")
    store = get_operational_store(db, user, template.store_id)
    return MessagePreviewResponse(
        rendered_content=render_template(
            template.content,
            name=payload.customer_name,
            product=payload.product,
            store=store.name,
        )
    )
