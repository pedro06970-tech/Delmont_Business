import math
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_operational_store, require_csrf
from app.core.errors import AppError
from app.db.session import get_db
from app.models.commercial import Customer, MessageTemplate, Reminder
from app.models.store import UserStore
from app.models.user import User, UserRole
from app.schemas.reminder import (
    ProductCancellationResponse,
    ProductSaleCompleted,
    ReminderCreate,
    ReminderPage,
    ReminderResponse,
    ReminderUpdate,
)
from app.schemas.whatsmiau import ReminderDeliveryAttemptResponse
from app.models.commercial import ReminderDeliveryAttempt
from app.services.reminders import (
    normalize_product,
    render_reminder_message,
    validate_reminder_sources,
)

router = APIRouter(prefix="/reminders", tags=["reminders"])
VALID_STATUSES = frozenset({"pending", "cancelled", "completed", "failed"})


def get_reminder_for_user(db: Session, user: User, reminder_id: uuid.UUID) -> Reminder:
    query = select(Reminder).where(Reminder.id == reminder_id)
    if user.role == UserRole.COLLABORATOR:
        query = query.join(UserStore, UserStore.store_id == Reminder.store_id).where(
            UserStore.user_id == user.id
        )
    reminder = db.scalar(query)
    if not reminder:
        raise AppError(404, "reminder_not_found", "Lembrete não encontrado ou não autorizado.")
    get_operational_store(db, user, reminder.store_id)
    return reminder


def commit_reminder(db: Session, reminder: Reminder) -> Reminder:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(
            409,
            "duplicate_reminder",
            "Já existe um lembrete pendente igual para esta data e horário.",
        )
    db.refresh(reminder)
    return reminder


@router.get("", response_model=ReminderPage)
def list_reminders(
    store_id: uuid.UUID,
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReminderPage:
    get_operational_store(db, user, store_id)
    if status is not None and status not in VALID_STATUSES:
        raise AppError(422, "invalid_reminder_status", "Status de lembrete inválido.")
    filters = [Reminder.store_id == store_id]
    if status:
        filters.append(Reminder.status == status)
    total = db.scalar(select(func.count(Reminder.id)).where(*filters)) or 0
    reminders = list(
        db.scalars(
            select(Reminder)
            .where(*filters)
            .order_by(Reminder.scheduled_for, Reminder.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return ReminderPage(
        items=[ReminderResponse.model_validate(reminder) for reminder in reminders],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("", response_model=ReminderResponse, status_code=201)
def create_reminder(
    payload: ReminderCreate,
    user: User = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> Reminder:
    store = get_operational_store(db, user, payload.store_id)
    customer, template = validate_reminder_sources(
        customer=db.get(Customer, payload.customer_id),
        template=db.get(MessageTemplate, payload.message_template_id),
        store=store,
    )
    reminder = Reminder(
        store_id=store.id,
        customer_id=customer.id,
        message_template_id=template.id,
        product_interest=payload.product_interest,
        product_key=normalize_product(payload.product_interest),
        scheduled_for=payload.scheduled_for,
        rendered_message=render_reminder_message(
            customer=customer,
            template=template,
            store=store,
            product=payload.product_interest,
        ),
        status="pending",
        created_by_user_id=user.id,
    )
    db.add(reminder)
    return commit_reminder(db, reminder)


@router.post("/cancel-product", response_model=ProductCancellationResponse)
def cancel_product_reminders(
    payload: ProductSaleCompleted,
    user: User = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> ProductCancellationResponse:
    get_operational_store(db, user, payload.store_id)
    customer = db.get(Customer, payload.customer_id)
    if not customer or customer.store_id != payload.store_id:
        raise AppError(404, "customer_not_found", "Cliente não encontrado nesta loja.")
    result = db.execute(
        update(Reminder)
        .where(
            Reminder.store_id == payload.store_id,
            Reminder.customer_id == payload.customer_id,
            Reminder.product_key == normalize_product(payload.product_interest),
            Reminder.status == "pending",
            Reminder.execution_status.in_(("pending", "claimed", "retry_wait")),
        )
        .values(status="cancelled", cancelled_at=datetime.now(UTC))
    )
    db.commit()
    return ProductCancellationResponse(cancelled_count=result.rowcount or 0)


@router.get("/{reminder_id}", response_model=ReminderResponse)
def get_reminder(
    reminder_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Reminder:
    return get_reminder_for_user(db, user, reminder_id)


@router.get(
    "/{reminder_id}/attempts", response_model=list[ReminderDeliveryAttemptResponse]
)
def list_reminder_attempts(
    reminder_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ReminderDeliveryAttempt]:
    reminder = get_reminder_for_user(db, user, reminder_id)
    return list(
        db.scalars(
            select(ReminderDeliveryAttempt)
            .where(
                ReminderDeliveryAttempt.reminder_id == reminder.id,
                ReminderDeliveryAttempt.store_id == reminder.store_id,
            )
            .order_by(ReminderDeliveryAttempt.attempt_number.desc())
        )
    )


@router.patch("/{reminder_id}", response_model=ReminderResponse)
def update_reminder(
    reminder_id: uuid.UUID,
    payload: ReminderUpdate,
    user: User = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> Reminder:
    reminder = get_reminder_for_user(db, user, reminder_id)
    if reminder.status != "pending" or reminder.execution_status not in (
        "pending",
        "retry_wait",
    ):
        raise AppError(409, "reminder_not_pending", "Somente lembretes pendentes podem ser editados.")
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise AppError(422, "empty_update", "Informe ao menos um campo para alterar.")
    store = get_operational_store(db, user, reminder.store_id)
    template_id = updates.get("message_template_id", reminder.message_template_id)
    product = updates.get("product_interest", reminder.product_interest)
    customer, template = validate_reminder_sources(
        customer=db.get(Customer, reminder.customer_id),
        template=db.get(MessageTemplate, template_id),
        store=store,
    )
    reminder.message_template_id = template.id
    reminder.product_interest = product
    reminder.product_key = normalize_product(product)
    if "scheduled_for" in updates:
        reminder.scheduled_for = updates["scheduled_for"]
    reminder.rendered_message = render_reminder_message(
        customer=customer, template=template, store=store, product=product
    )
    return commit_reminder(db, reminder)


@router.post("/{reminder_id}/cancel", response_model=ReminderResponse)
def cancel_reminder(
    reminder_id: uuid.UUID,
    user: User = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> Reminder:
    reminder = get_reminder_for_user(db, user, reminder_id)
    if reminder.status == "cancelled":
        return reminder
    if reminder.execution_status in ("sending", "uncertain"):
        raise AppError(
            409,
            "reminder_in_flight",
            "O envio já foi iniciado ou possui resultado incerto e não pode ser cancelado.",
        )
    if reminder.status != "pending":
        raise AppError(409, "reminder_not_pending", "Este lembrete não pode ser cancelado.")
    reminder.status = "cancelled"
    reminder.cancelled_at = datetime.now(UTC)
    db.commit()
    db.refresh(reminder)
    return reminder
