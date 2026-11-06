import math
import re
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_operational_store, require_csrf
from app.core.errors import AppError
from app.db.session import get_db
from app.models.commercial import ConsentEvent, Customer
from app.models.store import Store, UserStore
from app.models.user import User, UserRole
from app.schemas.commercial import (
    ConsentEventResponse,
    ConsentRequest,
    CustomerCreate,
    CustomerDetailResponse,
    CustomerPage,
    CustomerResponse,
    CustomerUpdate,
)
from app.services.commercial import normalize_phone

router = APIRouter(prefix="/customers", tags=["customers"])


def get_customer_for_user(
    db: Session, user: User, customer_id: uuid.UUID
) -> Customer:
    query = select(Customer).where(Customer.id == customer_id)
    if user.role == UserRole.COLLABORATOR:
        query = query.join(UserStore, UserStore.store_id == Customer.store_id).where(
            UserStore.user_id == user.id
        )
    customer = db.scalar(query)
    if not customer:
        raise AppError(404, "customer_not_found", "Cliente não encontrado ou não autorizado.")
    get_operational_store(db, user, customer.store_id)
    return customer


def customer_detail(customer: Customer) -> CustomerDetailResponse:
    base = CustomerResponse.model_validate(customer)
    return CustomerDetailResponse(
        **base.model_dump(),
        consent_history=[ConsentEventResponse.model_validate(event) for event in customer.consent_events],
    )


@router.get("", response_model=CustomerPage)
def list_customers(
    store_id: uuid.UUID,
    search: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustomerPage:
    get_operational_store(db, user, store_id)
    filters = [Customer.store_id == store_id]
    if search and search.strip():
        term = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{term}%"
        phone_term = re.sub(r"\D", "", search)
        phone_pattern = f"%{phone_term}%" if phone_term else pattern
        filters.append(
            or_(
                Customer.name.ilike(pattern, escape="\\"),
                Customer.phone_e164.ilike(phone_pattern, escape="\\"),
            )
        )
    total = db.scalar(select(func.count(Customer.id)).where(*filters)) or 0
    customers = list(
        db.scalars(
            select(Customer)
            .where(*filters)
            .order_by(Customer.name, Customer.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return CustomerPage(
        items=[CustomerResponse.model_validate(customer) for customer in customers],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("", response_model=CustomerResponse, status_code=201)
def create_customer(
    payload: CustomerCreate,
    user: User = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> Customer:
    get_operational_store(db, user, payload.store_id)
    customer = Customer(
        store_id=payload.store_id,
        name=payload.name,
        phone_e164=normalize_phone(payload.phone),
        notes=payload.notes,
        is_active=payload.is_active,
        has_consent=False,
        created_by_user_id=user.id,
    )
    db.add(customer)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "customer_phone_exists", "Este telefone já está cadastrado nesta loja.")
    db.refresh(customer)
    return customer


@router.get("/{customer_id}", response_model=CustomerDetailResponse)
def get_customer(
    customer_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustomerDetailResponse:
    return customer_detail(get_customer_for_user(db, user, customer_id))


@router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: uuid.UUID,
    payload: CustomerUpdate,
    user: User = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> Customer:
    customer = get_customer_for_user(db, user, customer_id)
    updates = payload.model_dump(exclude_unset=True)
    if "phone" in updates:
        updates["phone_e164"] = normalize_phone(updates.pop("phone"))
    for field, value in updates.items():
        setattr(customer, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "customer_phone_exists", "Este telefone já está cadastrado nesta loja.")
    db.refresh(customer)
    return customer


@router.post("/{customer_id}/consent", response_model=CustomerDetailResponse)
def grant_consent(
    customer_id: uuid.UUID,
    payload: ConsentRequest,
    user: User = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> CustomerDetailResponse:
    customer = get_customer_for_user(db, user, customer_id)
    if customer.has_consent:
        raise AppError(409, "consent_already_granted", "O consentimento já está ativo.")
    now = datetime.now(UTC)
    customer.has_consent = True
    customer.consented_at = now
    customer.consent_source = payload.source
    customer.consent_revoked_at = None
    customer.consent_events.append(
        ConsentEvent(action="granted", source=payload.source, performed_by_user_id=user.id)
    )
    db.commit()
    db.refresh(customer)
    return customer_detail(customer)


@router.post("/{customer_id}/revoke-consent", response_model=CustomerDetailResponse)
def revoke_consent(
    customer_id: uuid.UUID,
    user: User = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> CustomerDetailResponse:
    customer = get_customer_for_user(db, user, customer_id)
    if not customer.has_consent:
        raise AppError(409, "consent_not_active", "O cliente não possui consentimento ativo.")
    now = datetime.now(UTC)
    customer.has_consent = False
    customer.consent_revoked_at = now
    customer.consent_events.append(
        ConsentEvent(action="revoked", source=None, performed_by_user_id=user.id)
    )
    db.commit()
    db.refresh(customer)
    return customer_detail(customer)
