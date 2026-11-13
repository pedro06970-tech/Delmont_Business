import math
import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.dependencies import get_current_user, get_operational_store, require_csrf
from app.core.errors import AppError
from app.db.session import get_db
from app.models.commercial import (
    Customer,
    Reminder,
    SalesOpportunity,
    SalesOpportunityEvent,
)
from app.models.store import UserStore
from app.models.user import User, UserRole
from app.schemas.sales_opportunity import (
    CommercialDashboardResponse,
    SalesOpportunityClose,
    SalesOpportunityCreate,
    SalesOpportunityDetailResponse,
    SalesOpportunityEventResponse,
    SalesOpportunityPage,
    SalesOpportunityResponse,
    SalesOpportunityUpdate,
)
from app.services.reminders import normalize_product
from app.services.sales_opportunities import build_commercial_dashboard, normalize_period

router = APIRouter(prefix="/sales-opportunities", tags=["sales opportunities"])
dashboard_router = APIRouter(prefix="/commercial", tags=["commercial dashboard"])
VALID_STATUSES = frozenset({"open", "won", "lost"})


def opportunity_query():
    return select(SalesOpportunity).options(
        joinedload(SalesOpportunity.customer),
        joinedload(SalesOpportunity.created_by),
        joinedload(SalesOpportunity.closed_by),
    )


def get_opportunity_for_user(
    db: Session,
    user: User,
    opportunity_id: uuid.UUID,
    *,
    lock: bool = False,
    include_events: bool = False,
) -> SalesOpportunity:
    query = opportunity_query().where(SalesOpportunity.id == opportunity_id)
    if include_events:
        query = query.options(
            selectinload(SalesOpportunity.events).joinedload(
                SalesOpportunityEvent.performed_by
            )
        )
    if user.role == UserRole.COLLABORATOR:
        query = query.join(
            UserStore, UserStore.store_id == SalesOpportunity.store_id
        ).where(UserStore.user_id == user.id)
    if lock:
        query = query.with_for_update(of=SalesOpportunity)
    opportunity = db.scalar(query)
    if not opportunity:
        raise AppError(
            404,
            "sales_opportunity_not_found",
            "Oportunidade não encontrada ou não autorizada.",
        )
    get_operational_store(db, user, opportunity.store_id)
    return opportunity


def response_for(
    opportunity: SalesOpportunity, *, reminder_count: int = 0
) -> SalesOpportunityResponse:
    return SalesOpportunityResponse(
        id=opportunity.id,
        store_id=opportunity.store_id,
        customer_id=opportunity.customer_id,
        customer_name=opportunity.customer.name,
        product_name=opportunity.product_name,
        status=opportunity.status,
        created_by_user_id=opportunity.created_by_user_id,
        created_by_name=opportunity.created_by.name,
        closed_by_user_id=opportunity.closed_by_user_id,
        closed_by_name=opportunity.closed_by.name if opportunity.closed_by else None,
        created_at=opportunity.created_at,
        updated_at=opportunity.updated_at,
        closed_at=opportunity.closed_at,
        lost_reason=opportunity.lost_reason,
        reminder_count=reminder_count,
    )


def detail_for(db: Session, opportunity: SalesOpportunity) -> SalesOpportunityDetailResponse:
    reminder_count = db.scalar(
        select(func.count(Reminder.id)).where(Reminder.opportunity_id == opportunity.id)
    ) or 0
    base = response_for(opportunity, reminder_count=reminder_count)
    return SalesOpportunityDetailResponse(
        **base.model_dump(),
        events=[
            SalesOpportunityEventResponse(
                id=event.id,
                previous_status=event.previous_status,
                new_status=event.new_status,
                performed_by_user_id=event.performed_by_user_id,
                performed_by_name=event.performed_by.name,
                lost_reason=event.lost_reason,
                occurred_at=event.occurred_at,
            )
            for event in opportunity.events
        ],
    )


@router.get("", response_model=SalesOpportunityPage)
def list_sales_opportunities(
    store_id: uuid.UUID,
    status: str | None = Query(default=None),
    created_by_user_id: uuid.UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SalesOpportunityPage:
    get_operational_store(db, user, store_id)
    if status is not None and status not in VALID_STATUSES:
        raise AppError(422, "invalid_opportunity_status", "Status de oportunidade inválido.")
    filters = [SalesOpportunity.store_id == store_id]
    if status:
        filters.append(SalesOpportunity.status == status)
    if created_by_user_id:
        filters.append(SalesOpportunity.created_by_user_id == created_by_user_id)
    if date_from or date_to:
        _, _, start_utc, end_utc = normalize_period(date_from, date_to)
        filters.extend(
            [SalesOpportunity.created_at >= start_utc, SalesOpportunity.created_at < end_utc]
        )
    reminder_count = (
        select(func.count(Reminder.id))
        .where(Reminder.opportunity_id == SalesOpportunity.id)
        .correlate(SalesOpportunity)
        .scalar_subquery()
    )
    total = db.scalar(select(func.count(SalesOpportunity.id)).where(*filters)) or 0
    rows = db.execute(
        opportunity_query()
        .add_columns(reminder_count.label("reminder_count"))
        .where(*filters)
        .order_by(SalesOpportunity.created_at.desc(), SalesOpportunity.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return SalesOpportunityPage(
        items=[response_for(opportunity, reminder_count=count) for opportunity, count in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("", response_model=SalesOpportunityDetailResponse, status_code=201)
def create_sales_opportunity(
    payload: SalesOpportunityCreate,
    user: User = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> SalesOpportunityDetailResponse:
    get_operational_store(db, user, payload.store_id)
    customer = db.get(Customer, payload.customer_id)
    if not customer or customer.store_id != payload.store_id:
        raise AppError(404, "customer_not_found", "Cliente não encontrado nesta loja.")
    if not customer.is_active:
        raise AppError(409, "inactive_customer", "O cliente está inativo.")
    opportunity = SalesOpportunity(
        store_id=payload.store_id,
        customer_id=payload.customer_id,
        product_name=payload.product_name,
        product_key=normalize_product(payload.product_name),
        status="open",
        created_by_user_id=user.id,
    )
    opportunity.events.append(
        SalesOpportunityEvent(
            previous_status=None,
            new_status="open",
            performed_by_user_id=user.id,
        )
    )
    db.add(opportunity)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(
            409,
            "duplicate_open_opportunity",
            "Já existe uma oportunidade aberta para este cliente e produto.",
        )
    opportunity = get_opportunity_for_user(
        db, user, opportunity.id, include_events=True
    )
    return detail_for(db, opportunity)


@router.get("/{opportunity_id}", response_model=SalesOpportunityDetailResponse)
def get_sales_opportunity(
    opportunity_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SalesOpportunityDetailResponse:
    opportunity = get_opportunity_for_user(
        db, user, opportunity_id, include_events=True
    )
    return detail_for(db, opportunity)


@router.patch("/{opportunity_id}", response_model=SalesOpportunityDetailResponse)
def update_sales_opportunity(
    opportunity_id: uuid.UUID,
    payload: SalesOpportunityUpdate,
    user: User = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> SalesOpportunityDetailResponse:
    opportunity = get_opportunity_for_user(db, user, opportunity_id, lock=True)
    if opportunity.status != "open":
        raise AppError(409, "opportunity_closed", "Oportunidades encerradas não podem ser editadas.")
    linked_reminders = db.scalar(
        select(func.count(Reminder.id)).where(Reminder.opportunity_id == opportunity.id)
    ) or 0
    if linked_reminders:
        raise AppError(
            409,
            "opportunity_has_reminders",
            "O produto não pode ser alterado após associar lembretes à oportunidade.",
        )
    opportunity.product_name = payload.product_name
    opportunity.product_key = normalize_product(payload.product_name)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(
            409,
            "duplicate_open_opportunity",
            "Já existe uma oportunidade aberta para este cliente e produto.",
        )
    opportunity = get_opportunity_for_user(
        db, user, opportunity_id, include_events=True
    )
    return detail_for(db, opportunity)


@router.post("/{opportunity_id}/close", response_model=SalesOpportunityDetailResponse)
def close_sales_opportunity(
    opportunity_id: uuid.UUID,
    payload: SalesOpportunityClose,
    user: User = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> SalesOpportunityDetailResponse:
    opportunity = get_opportunity_for_user(db, user, opportunity_id, lock=True)
    if opportunity.status != "open":
        if opportunity.status != payload.status:
            raise AppError(
                409,
                "opportunity_already_closed",
                "A oportunidade já foi encerrada com outro resultado.",
            )
        db.rollback()
        opportunity = get_opportunity_for_user(
            db, user, opportunity_id, include_events=True
        )
        return detail_for(db, opportunity)

    now = datetime.now(UTC)
    opportunity.status = payload.status
    opportunity.closed_by_user_id = user.id
    opportunity.closed_at = now
    opportunity.lost_reason = payload.lost_reason if payload.status == "lost" else None
    opportunity.events.append(
        SalesOpportunityEvent(
            previous_status="open",
            new_status=payload.status,
            performed_by_user_id=user.id,
            lost_reason=opportunity.lost_reason,
            occurred_at=now,
        )
    )
    db.execute(
        update(Reminder)
        .where(
            Reminder.opportunity_id == opportunity.id,
            Reminder.status == "pending",
            Reminder.execution_status.in_(("pending", "claimed", "retry_wait")),
        )
        .values(
            status="cancelled",
            execution_status="pending",
            cancelled_at=now,
            claim_token=None,
            claimed_at=None,
            lease_expires_at=None,
            next_attempt_at=None,
        )
    )
    db.commit()
    opportunity = get_opportunity_for_user(
        db, user, opportunity_id, include_events=True
    )
    return detail_for(db, opportunity)


@dashboard_router.get("/dashboard", response_model=CommercialDashboardResponse)
def commercial_dashboard(
    store_id: uuid.UUID,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    created_by_user_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CommercialDashboardResponse:
    get_operational_store(db, user, store_id)
    return build_commercial_dashboard(
        db,
        store_id=store_id,
        date_from=date_from,
        date_to=date_to,
        created_by_user_id=created_by_user_id,
    )
