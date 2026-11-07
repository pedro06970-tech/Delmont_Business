import os
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_user,
    get_operational_store,
    require_admin,
    require_admin_csrf,
    require_csrf,
)
from app.core.config import settings
from app.core.errors import AppError
from app.db.session import get_db
from app.integrations.whatsmiau import WhatsMiauClient, WhatsMiauError, resolve_credential
from app.models.commercial import ReminderDeliveryAttempt, WhatsMiauConfiguration
from app.models.store import Store
from app.models.user import User
from app.schemas.whatsmiau import (
    HomologationNumberRequest,
    ReminderDeliveryAttemptResponse,
    WhatsMiauConfigurationResponse,
    WhatsMiauConfigurationUpsert,
    WhatsMiauReadinessResponse,
)
from app.services.commercial import normalize_phone

router = APIRouter(prefix="/whatsmiau", tags=["WhatsMiau"])


def get_store(db: Session, store_id: uuid.UUID) -> Store:
    store = db.get(Store, store_id)
    if not store:
        raise AppError(404, "store_not_found", "Loja não encontrada.")
    return store


def get_configuration(db: Session, store_id: uuid.UUID) -> WhatsMiauConfiguration:
    configuration = db.scalar(
        select(WhatsMiauConfiguration).where(WhatsMiauConfiguration.store_id == store_id)
    )
    if not configuration:
        raise AppError(404, "whatsmiau_not_configured", "Integração WhatsMiau não configurada.")
    return configuration


def configuration_response(
    configuration: WhatsMiauConfiguration,
) -> WhatsMiauConfigurationResponse:
    phone = configuration.homologation_phone_e164
    masked_phone = f"***{phone[-4:]}" if phone else None
    return WhatsMiauConfigurationResponse(
        id=configuration.id,
        store_id=configuration.store_id,
        instance_name=configuration.instance_name,
        is_enabled=configuration.is_enabled,
        dispatch_paused=configuration.dispatch_paused,
        connection_state=configuration.connection_state,
        last_connection_error=configuration.last_connection_error,
        last_checked_at=configuration.last_checked_at,
        last_dispatch_at=configuration.last_dispatch_at,
        credential_configured=bool(os.environ.get(configuration.credential_env_var, "").strip()),
        webhook_secret_configured=bool(
            configuration.webhook_secret_env_var
            and os.environ.get(configuration.webhook_secret_env_var, "").strip()
        ),
        homologation_ready=bool(phone and configuration.homologation_authorized_at),
        homologation_phone_masked=masked_phone,
        created_at=configuration.created_at,
        updated_at=configuration.updated_at,
    )


@router.get(
    "/configurations/{store_id}", response_model=WhatsMiauConfigurationResponse
)
def read_configuration(
    store_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WhatsMiauConfigurationResponse:
    get_store(db, store_id)
    return configuration_response(get_configuration(db, store_id))


@router.put(
    "/configurations/{store_id}", response_model=WhatsMiauConfigurationResponse
)
def upsert_configuration(
    store_id: uuid.UUID,
    payload: WhatsMiauConfigurationUpsert,
    _admin: User = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
) -> WhatsMiauConfigurationResponse:
    get_store(db, store_id)
    configuration = db.scalar(
        select(WhatsMiauConfiguration).where(WhatsMiauConfiguration.store_id == store_id)
    )
    if not configuration:
        configuration = WhatsMiauConfiguration(
            store_id=store_id,
            instance_name=payload.instance_name,
            credential_env_var=payload.credential_env_var,
            webhook_secret_env_var=payload.webhook_secret_env_var,
            is_enabled=payload.is_enabled,
            dispatch_paused=False,
            connection_state="unknown",
        )
        db.add(configuration)
    else:
        changed = (
            configuration.instance_name != payload.instance_name
            or configuration.credential_env_var != payload.credential_env_var
        )
        configuration.instance_name = payload.instance_name
        configuration.credential_env_var = payload.credential_env_var
        if payload.webhook_secret_env_var is not None:
            configuration.webhook_secret_env_var = payload.webhook_secret_env_var
        configuration.is_enabled = payload.is_enabled
        if changed:
            configuration.connection_state = "unknown"
            configuration.last_connection_error = None
            configuration.last_checked_at = None
    db.commit()
    db.refresh(configuration)
    return configuration_response(configuration)


def readiness_response(
    configuration: WhatsMiauConfiguration | None, store_id: uuid.UUID
) -> WhatsMiauReadinessResponse:
    credential_configured = bool(
        configuration
        and os.environ.get(configuration.credential_env_var, "").strip()
    )
    homologation_ready = bool(
        configuration
        and configuration.homologation_phone_e164
        and configuration.homologation_authorized_at
    )
    enabled = bool(configuration and configuration.is_enabled)
    paused = bool(configuration and configuration.dispatch_paused)
    connection_state = configuration.connection_state if configuration else "not_configured"
    return WhatsMiauReadinessResponse(
        store_id=store_id,
        configured=configuration is not None,
        enabled=enabled,
        dispatch_paused=paused,
        connection_state=connection_state,
        last_checked_at=configuration.last_checked_at if configuration else None,
        credential_configured=credential_configured,
        ready_to_schedule=bool(
            configuration
            and enabled
            and not paused
            and connection_state == "open"
            and credential_configured
            and (not settings.REMINDER_HOMOLOGATION_ONLY or homologation_ready)
        ),
        homologation_only=settings.REMINDER_HOMOLOGATION_ONLY,
        homologation_ready=homologation_ready,
    )


@router.get("/readiness/{store_id}", response_model=WhatsMiauReadinessResponse)
def read_readiness(
    store_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WhatsMiauReadinessResponse:
    get_operational_store(db, user, store_id)
    configuration = db.scalar(
        select(WhatsMiauConfiguration).where(WhatsMiauConfiguration.store_id == store_id)
    )
    return readiness_response(configuration, store_id)


def perform_connection_check(
    db: Session, configuration: WhatsMiauConfiguration
) -> None:
    now = datetime.now(UTC)
    try:
        api_key = resolve_credential(configuration.credential_env_var)
        state = WhatsMiauClient().connection_state(configuration.instance_name, api_key).state
    except WhatsMiauError as error:
        configuration.connection_state = "error"
        configuration.last_connection_error = error.safe_message
        configuration.last_checked_at = now
        db.commit()
        raise AppError(502, "whatsmiau_connection_failed", error.safe_message)
    configuration.connection_state = state
    configuration.last_connection_error = None
    configuration.last_checked_at = now
    db.commit()


@router.post("/readiness/{store_id}/check", response_model=WhatsMiauReadinessResponse)
def check_operational_readiness(
    store_id: uuid.UUID,
    user: User = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> WhatsMiauReadinessResponse:
    get_operational_store(db, user, store_id)
    configuration = get_configuration(db, store_id)
    perform_connection_check(db, configuration)
    db.refresh(configuration)
    return readiness_response(configuration, store_id)


@router.post(
    "/configurations/{store_id}/check", response_model=WhatsMiauConfigurationResponse
)
def check_connection(
    store_id: uuid.UUID,
    _admin: User = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
) -> WhatsMiauConfigurationResponse:
    configuration = get_configuration(db, store_id)
    perform_connection_check(db, configuration)
    db.refresh(configuration)
    return configuration_response(configuration)


@router.put(
    "/configurations/{store_id}/homologation-number",
    response_model=WhatsMiauConfigurationResponse,
)
def authorize_homologation_number(
    store_id: uuid.UUID,
    payload: HomologationNumberRequest,
    _admin: User = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
) -> WhatsMiauConfigurationResponse:
    configuration = get_configuration(db, store_id)
    configuration.homologation_phone_e164 = normalize_phone(payload.phone)
    configuration.homologation_authorized_at = datetime.now(UTC)
    db.commit()
    db.refresh(configuration)
    return configuration_response(configuration)


def set_pause(
    db: Session, store_id: uuid.UUID, *, paused: bool
) -> WhatsMiauConfigurationResponse:
    configuration = get_configuration(db, store_id)
    configuration.dispatch_paused = paused
    db.commit()
    db.refresh(configuration)
    return configuration_response(configuration)


@router.post(
    "/configurations/{store_id}/pause", response_model=WhatsMiauConfigurationResponse
)
def pause_dispatches(
    store_id: uuid.UUID,
    _admin: User = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
) -> WhatsMiauConfigurationResponse:
    return set_pause(db, store_id, paused=True)


@router.post(
    "/configurations/{store_id}/resume", response_model=WhatsMiauConfigurationResponse
)
def resume_dispatches(
    store_id: uuid.UUID,
    _admin: User = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
) -> WhatsMiauConfigurationResponse:
    return set_pause(db, store_id, paused=False)


@router.get("/attempts", response_model=list[ReminderDeliveryAttemptResponse])
def list_attempts(
    store_id: uuid.UUID,
    status: str | None = Query(default=None, max_length=16),
    reminder_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[ReminderDeliveryAttempt]:
    get_store(db, store_id)
    query = select(ReminderDeliveryAttempt).where(
        ReminderDeliveryAttempt.store_id == store_id
    )
    if status:
        query = query.where(ReminderDeliveryAttempt.status == status)
    if reminder_id:
        query = query.where(ReminderDeliveryAttempt.reminder_id == reminder_id)
    return list(
        db.scalars(
            query.order_by(ReminderDeliveryAttempt.started_at.desc()).limit(limit)
        )
    )


@router.get(
    "/attempts/{attempt_id}", response_model=ReminderDeliveryAttemptResponse
)
def get_attempt(
    attempt_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ReminderDeliveryAttempt:
    attempt = db.get(ReminderDeliveryAttempt, attempt_id)
    if not attempt:
        raise AppError(404, "attempt_not_found", "Tentativa não encontrada.")
    return attempt
