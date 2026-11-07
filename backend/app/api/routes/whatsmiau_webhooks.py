import os
import secrets
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_db
from app.models.commercial import (
    Reminder,
    ReminderDeliveryAttempt,
    WhatsMiauConfiguration,
)
from app.schemas.whatsmiau import WhatsMiauWebhookEnvelope, WhatsMiauWebhookResponse

router = APIRouter(prefix="/webhooks/whatsmiau", tags=["WhatsMiau webhooks"])


@router.post("/{store_id}", response_model=WhatsMiauWebhookResponse)
def receive_delivery_update(
    store_id: uuid.UUID,
    payload: WhatsMiauWebhookEnvelope,
    webhook_secret: str | None = Header(default=None, alias="X-Delmont-Webhook-Secret"),
    db: Session = Depends(get_db),
) -> WhatsMiauWebhookResponse:
    configuration = db.scalar(
        select(WhatsMiauConfiguration).where(
            WhatsMiauConfiguration.store_id == store_id
        )
    )
    expected = (
        os.environ.get(configuration.webhook_secret_env_var, "").strip()
        if configuration and configuration.webhook_secret_env_var
        else ""
    )
    if (
        not configuration
        or not expected
        or not webhook_secret
        or not secrets.compare_digest(expected, webhook_secret)
    ):
        raise AppError(401, "invalid_webhook_secret", "Webhook não autorizado.")
    if payload.instance != configuration.instance_name:
        raise AppError(404, "webhook_instance_not_found", "Instância não reconhecida.")
    if payload.event != "messages.update" or payload.data.status not in (
        "DELIVERY_ACK",
        "READ",
    ):
        return WhatsMiauWebhookResponse(processed=False)
    message_id = payload.data.messageId or payload.data.keyId
    if not message_id:
        return WhatsMiauWebhookResponse(processed=False)
    reminder = db.scalar(
        select(Reminder)
        .where(
            Reminder.store_id == store_id,
            Reminder.provider_message_id == message_id,
        )
        .with_for_update()
    )
    if not reminder:
        return WhatsMiauWebhookResponse(processed=False)
    now = datetime.now(UTC)
    reminder.delivered_at = reminder.delivered_at or now
    reminder.provider_status = "delivered"
    if payload.data.status == "READ":
        reminder.read_at = reminder.read_at or now
        reminder.provider_status = "read"
    attempt = db.scalar(
        select(ReminderDeliveryAttempt)
        .where(
            ReminderDeliveryAttempt.reminder_id == reminder.id,
            ReminderDeliveryAttempt.provider_message_id == message_id,
        )
        .order_by(ReminderDeliveryAttempt.attempt_number.desc())
        .limit(1)
        .with_for_update()
    )
    if attempt:
        attempt.delivered_at = attempt.delivered_at or now
        attempt.provider_status = reminder.provider_status
        if payload.data.status == "READ":
            attempt.read_at = attempt.read_at or now
    db.commit()
    return WhatsMiauWebhookResponse(processed=True)
