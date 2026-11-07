import logging
import signal
import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.integrations.whatsmiau import WhatsMiauClient, WhatsMiauError, resolve_credential
from app.models.commercial import (
    Customer,
    Reminder,
    ReminderDeliveryAttempt,
    WhatsMiauConfiguration,
)
from app.models.store import Store

logger = logging.getLogger("delmont.reminder_worker")
ACTIVE_EXECUTION_STATES = ("pending", "retry_wait")


def _clear_claim(reminder: Reminder) -> None:
    reminder.claim_token = None
    reminder.claimed_at = None
    reminder.lease_expires_at = None


def _next_attempt_number(db: Session, reminder_id: uuid.UUID) -> int:
    current = db.scalar(
        select(func.max(ReminderDeliveryAttempt.attempt_number)).where(
            ReminderDeliveryAttempt.reminder_id == reminder_id
        )
    )
    return (current or 0) + 1


def _record_without_send(
    db: Session,
    reminder: Reminder,
    configuration: WhatsMiauConfiguration | None,
    *,
    status: str,
    category: str,
    message: str,
    now: datetime,
) -> None:
    db.add(
        ReminderDeliveryAttempt(
            reminder_id=reminder.id,
            store_id=reminder.store_id,
            configuration_id=configuration.id if configuration else None,
            attempt_number=_next_attempt_number(db, reminder.id),
            status=status,
            error_category=category,
            sanitized_error=message,
            started_at=now,
            finished_at=now,
        )
    )
    reminder.last_attempt_at = now
    reminder.last_transport_error = message


def _mark_terminal_failure(
    reminder: Reminder, *, message: str, now: datetime
) -> None:
    reminder.execution_status = "failed"
    reminder.status = "failed"
    reminder.failed_at = now
    reminder.failure_reason = message
    reminder.last_transport_error = message
    reminder.next_attempt_at = None
    _clear_claim(reminder)


def recover_expired_claims(db: Session, now: datetime) -> tuple[int, int]:
    expired = list(
        db.scalars(
            select(Reminder)
            .where(
                Reminder.execution_status.in_(("claimed", "sending")),
                Reminder.lease_expires_at <= now,
            )
            .with_for_update(skip_locked=True)
        )
    )
    released = 0
    uncertain = 0
    for reminder in expired:
        if reminder.execution_status == "sending":
            reminder.execution_status = "uncertain"
            reminder.last_transport_error = (
                "O worker reiniciou durante o envio; o resultado precisa de análise manual."
            )
            active_attempt = db.scalar(
                select(ReminderDeliveryAttempt)
                .where(
                    ReminderDeliveryAttempt.reminder_id == reminder.id,
                    ReminderDeliveryAttempt.status == "started",
                )
                .order_by(ReminderDeliveryAttempt.attempt_number.desc())
                .limit(1)
                .with_for_update()
            )
            if active_attempt:
                active_attempt.status = "uncertain"
                active_attempt.error_category = "expired_sending_lease"
                active_attempt.sanitized_error = reminder.last_transport_error
                active_attempt.finished_at = now
            uncertain += 1
        else:
            reminder.execution_status = "pending"
            reminder.next_attempt_at = now
            released += 1
        _clear_claim(reminder)
    db.commit()
    return released, uncertain


def claim_due_reminders(db: Session, now: datetime, batch_size: int) -> list[tuple[uuid.UUID, uuid.UUID]]:
    due = list(
        db.scalars(
            select(Reminder)
            .join(Store, Store.id == Reminder.store_id)
            .where(
                Reminder.status == "pending",
                Reminder.scheduled_for <= now,
                Reminder.execution_status.in_(ACTIVE_EXECUTION_STATES),
                or_(Reminder.next_attempt_at.is_(None), Reminder.next_attempt_at <= now),
                Store.is_active.is_(True),
            )
            .order_by(Reminder.scheduled_for, Reminder.id)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
    )
    claimed: list[tuple[uuid.UUID, uuid.UUID]] = []
    lease_until = now + timedelta(seconds=settings.REMINDER_CLAIM_TTL_SECONDS)
    for reminder in due:
        token = uuid.uuid4()
        reminder.execution_status = "claimed"
        reminder.claim_token = token
        reminder.claimed_at = now
        reminder.lease_expires_at = lease_until
        claimed.append((reminder.id, token))
    db.commit()
    return claimed


class ReminderWorker:
    def __init__(self, client: WhatsMiauClient | None = None) -> None:
        self.client = client or WhatsMiauClient()

    def run_once(self, *, now: datetime | None = None) -> int:
        if not settings.REMINDER_DISPATCH_ENABLED:
            return 0
        operation_time = now or datetime.now(UTC)
        with SessionLocal() as db:
            recover_expired_claims(db, operation_time)
            claims = claim_due_reminders(
                db, operation_time, settings.REMINDER_WORKER_BATCH_SIZE
            )
        for reminder_id, claim_token in claims:
            self.process_claim(reminder_id, claim_token, now=operation_time)
        return len(claims)

    def process_claim(
        self, reminder_id: uuid.UUID, claim_token: uuid.UUID, *, now: datetime
    ) -> None:
        prepared = self._validate_claim(reminder_id, claim_token, now=now)
        if not prepared:
            return
        instance_name, credential_reference = prepared
        try:
            api_key = resolve_credential(credential_reference)
        except WhatsMiauError as error:
            self._fail_preflight(reminder_id, claim_token, error, now=now)
            return

        try:
            connection = self.client.connection_state(instance_name, api_key)
        except WhatsMiauError as error:
            if error.safe_to_retry:
                self._defer_preflight(reminder_id, claim_token, error, now=now)
            else:
                self._fail_preflight(reminder_id, claim_token, error, now=now)
            return
        self._save_connection_state(reminder_id, connection.state, now=now)
        if connection.state != "open":
            self._defer_disconnected(reminder_id, claim_token, connection.state, now=now)
            return

        attempt_id = self._reserve_send(reminder_id, claim_token, now=now)
        if not attempt_id:
            return
        with SessionLocal() as db:
            reminder = db.get(Reminder, reminder_id)
            customer = db.get(Customer, reminder.customer_id) if reminder else None
            configuration = db.scalar(
                select(WhatsMiauConfiguration).where(
                    WhatsMiauConfiguration.store_id == reminder.store_id
                )
            ) if reminder else None
            if not reminder or not customer or not configuration:
                return
            number = customer.phone_e164
            message = reminder.rendered_message
            instance_name = configuration.instance_name

        try:
            result = self.client.send_text(
                instance_name,
                api_key,
                number=number,
                text=message,
            )
        except WhatsMiauError as error:
            self._finish_error(reminder_id, claim_token, attempt_id, error, now=now)
            return
        self._finish_success(reminder_id, claim_token, attempt_id, result, now=now)

    def _validate_claim(
        self, reminder_id: uuid.UUID, claim_token: uuid.UUID, *, now: datetime
    ) -> tuple[str, str] | None:
        with SessionLocal() as db:
            reminder = db.scalar(
                select(Reminder).where(Reminder.id == reminder_id).with_for_update()
            )
            if (
                not reminder
                or reminder.claim_token != claim_token
                or reminder.execution_status != "claimed"
            ):
                return None
            if reminder.status != "pending":
                _clear_claim(reminder)
                db.commit()
                return None
            customer = db.get(Customer, reminder.customer_id)
            store = db.get(Store, reminder.store_id)
            configuration = db.scalar(
                select(WhatsMiauConfiguration).where(
                    WhatsMiauConfiguration.store_id == reminder.store_id
                )
            )
            validation_error = None
            if not store or not store.is_active:
                validation_error = "A loja está inativa."
            elif not customer or not customer.is_active:
                validation_error = "O cliente está inativo."
            elif not customer.has_consent:
                validation_error = "O cliente não possui consentimento ativo."
            elif not configuration or not configuration.is_enabled:
                validation_error = "A integração WhatsMiau não está configurada e ativa."
            if validation_error:
                _record_without_send(
                    db,
                    reminder,
                    configuration,
                    status="skipped",
                    category="validation",
                    message=validation_error,
                    now=now,
                )
                _mark_terminal_failure(reminder, message=validation_error, now=now)
                db.commit()
                return None
            if settings.REMINDER_HOMOLOGATION_ONLY and (
                not configuration.homologation_authorized_at
                or customer.phone_e164 != configuration.homologation_phone_e164
            ):
                reminder.execution_status = "pending"
                reminder.next_attempt_at = now + timedelta(
                    seconds=settings.REMINDER_RETRY_BASE_SECONDS
                )
                reminder.last_transport_error = (
                    "Modo de homologação ativo: destinatário não autorizado para teste."
                )
                _clear_claim(reminder)
                db.commit()
                return None
            if configuration.dispatch_paused:
                reminder.execution_status = "pending"
                reminder.next_attempt_at = now + timedelta(
                    seconds=settings.REMINDER_RETRY_BASE_SECONDS
                )
                _clear_claim(reminder)
                db.commit()
                return None
            return configuration.instance_name, configuration.credential_env_var

    def _save_connection_state(self, reminder_id: uuid.UUID, state: str, *, now: datetime) -> None:
        with SessionLocal() as db:
            reminder = db.get(Reminder, reminder_id)
            if not reminder:
                return
            configuration = db.scalar(
                select(WhatsMiauConfiguration).where(
                    WhatsMiauConfiguration.store_id == reminder.store_id
                )
            )
            if configuration:
                configuration.connection_state = state[:32]
                configuration.last_connection_error = None
                configuration.last_checked_at = now
                db.commit()

    def _fail_preflight(
        self,
        reminder_id: uuid.UUID,
        claim_token: uuid.UUID,
        error: WhatsMiauError,
        *,
        now: datetime,
    ) -> None:
        with SessionLocal() as db:
            reminder = db.scalar(select(Reminder).where(Reminder.id == reminder_id).with_for_update())
            if not reminder or reminder.claim_token != claim_token:
                return
            configuration = db.scalar(select(WhatsMiauConfiguration).where(WhatsMiauConfiguration.store_id == reminder.store_id))
            _record_without_send(db, reminder, configuration, status="failed", category=error.category, message=error.safe_message, now=now)
            _mark_terminal_failure(reminder, message=error.safe_message, now=now)
            db.commit()

    def _defer_preflight(
        self,
        reminder_id: uuid.UUID,
        claim_token: uuid.UUID,
        error: WhatsMiauError,
        *,
        now: datetime,
    ) -> None:
        with SessionLocal() as db:
            reminder = db.scalar(select(Reminder).where(Reminder.id == reminder_id).with_for_update())
            if not reminder or reminder.claim_token != claim_token:
                return
            configuration = db.scalar(select(WhatsMiauConfiguration).where(WhatsMiauConfiguration.store_id == reminder.store_id))
            _record_without_send(db, reminder, configuration, status="retry_wait", category=error.category, message=error.safe_message, now=now)
            reminder.execution_status = "retry_wait"
            reminder.next_attempt_at = now + timedelta(seconds=settings.REMINDER_RETRY_BASE_SECONDS)
            _clear_claim(reminder)
            if configuration:
                configuration.connection_state = "error"
                configuration.last_connection_error = error.safe_message
                configuration.last_checked_at = now
            db.commit()

    def _defer_disconnected(
        self,
        reminder_id: uuid.UUID,
        claim_token: uuid.UUID,
        state: str,
        *,
        now: datetime,
    ) -> None:
        with SessionLocal() as db:
            reminder = db.scalar(select(Reminder).where(Reminder.id == reminder_id).with_for_update())
            if not reminder or reminder.claim_token != claim_token:
                return
            configuration = db.scalar(select(WhatsMiauConfiguration).where(WhatsMiauConfiguration.store_id == reminder.store_id))
            message = f"A instância WhatsMiau está desconectada ({state[:32]})."
            _record_without_send(db, reminder, configuration, status="disconnected", category="disconnected", message=message, now=now)
            reminder.execution_status = "retry_wait"
            reminder.next_attempt_at = now + timedelta(seconds=settings.REMINDER_RETRY_BASE_SECONDS)
            _clear_claim(reminder)
            db.commit()

    def _reserve_send(
        self, reminder_id: uuid.UUID, claim_token: uuid.UUID, *, now: datetime
    ) -> uuid.UUID | None:
        with SessionLocal() as db:
            reminder = db.scalar(select(Reminder).where(Reminder.id == reminder_id).with_for_update())
            if not reminder or reminder.claim_token != claim_token or reminder.status != "pending":
                return None
            configuration = db.scalar(
                select(WhatsMiauConfiguration)
                .where(WhatsMiauConfiguration.store_id == reminder.store_id)
                .with_for_update()
            )
            customer = db.get(Customer, reminder.customer_id)
            if not configuration or configuration.dispatch_paused or not customer or not customer.is_active or not customer.has_consent:
                reminder.execution_status = "pending"
                reminder.next_attempt_at = now + timedelta(seconds=settings.REMINDER_RETRY_BASE_SECONDS)
                _clear_claim(reminder)
                db.commit()
                return None
            active_sends = db.scalar(
                select(func.count(Reminder.id)).where(
                    Reminder.store_id == reminder.store_id,
                    Reminder.execution_status == "sending",
                    Reminder.lease_expires_at > now,
                )
            ) or 0
            interval_ready_at = (
                configuration.last_dispatch_at
                + timedelta(seconds=settings.REMINDER_MIN_INTERVAL_SECONDS)
                if configuration.last_dispatch_at
                else now
            )
            if active_sends >= settings.REMINDER_INSTANCE_CONCURRENCY or interval_ready_at > now:
                reminder.execution_status = "retry_wait"
                reminder.next_attempt_at = max(
                    interval_ready_at,
                    now + timedelta(seconds=max(settings.REMINDER_MIN_INTERVAL_SECONDS, 0.1)),
                )
                _clear_claim(reminder)
                db.commit()
                return None
            reminder.attempt_count += 1
            reminder.execution_status = "sending"
            reminder.last_attempt_at = now
            reminder.lease_expires_at = now + timedelta(seconds=settings.REMINDER_CLAIM_TTL_SECONDS)
            attempt = ReminderDeliveryAttempt(
                reminder_id=reminder.id,
                store_id=reminder.store_id,
                configuration_id=configuration.id,
                attempt_number=_next_attempt_number(db, reminder.id),
                status="started",
                started_at=now,
            )
            db.add(attempt)
            configuration.last_dispatch_at = now
            db.commit()
            return attempt.id

    def _finish_success(self, reminder_id, claim_token, attempt_id, result, *, now) -> None:
        with SessionLocal() as db:
            reminder = db.scalar(select(Reminder).where(Reminder.id == reminder_id).with_for_update())
            attempt = db.get(ReminderDeliveryAttempt, attempt_id)
            if not reminder or not attempt or reminder.claim_token != claim_token:
                return
            attempt.status = "accepted"
            attempt.provider_message_id = result.provider_message_id
            attempt.provider_status = result.provider_status
            attempt.finished_at = now
            reminder.execution_status = "sent"
            reminder.status = "completed"
            reminder.completed_at = now
            reminder.accepted_at = now
            reminder.provider_message_id = result.provider_message_id
            reminder.provider_status = result.provider_status
            reminder.last_transport_error = None
            reminder.next_attempt_at = None
            _clear_claim(reminder)
            db.commit()

    def _finish_error(self, reminder_id, claim_token, attempt_id, error, *, now) -> None:
        with SessionLocal() as db:
            reminder = db.scalar(select(Reminder).where(Reminder.id == reminder_id).with_for_update())
            attempt = db.get(ReminderDeliveryAttempt, attempt_id)
            if not reminder or not attempt or reminder.claim_token != claim_token:
                return
            attempt.error_category = error.category
            attempt.sanitized_error = error.safe_message
            attempt.http_status = error.http_status
            attempt.finished_at = now
            reminder.last_transport_error = error.safe_message
            if error.ambiguous:
                attempt.status = "uncertain"
                reminder.execution_status = "uncertain"
                reminder.next_attempt_at = None
            elif error.safe_to_retry and reminder.attempt_count < settings.REMINDER_MAX_ATTEMPTS:
                attempt.status = "retry_wait"
                reminder.execution_status = "retry_wait"
                delay = settings.REMINDER_RETRY_BASE_SECONDS * (2 ** (reminder.attempt_count - 1))
                reminder.next_attempt_at = now + timedelta(seconds=delay)
            else:
                attempt.status = "failed"
                _mark_terminal_failure(reminder, message=error.safe_message, now=now)
            _clear_claim(reminder)
            db.commit()

    @staticmethod
    def reconcile_uncertain() -> int:
        # A documentação oficial não oferece consulta confiável por ID para reconciliar envios.
        # Manter uncertain evita um reenvio possivelmente duplicado.
        return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    stopping = False

    def stop(_signum, _frame) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    worker = ReminderWorker()
    logger.info("Reminder worker started")
    while not stopping:
        try:
            worker.run_once()
        except Exception:
            logger.exception("Reminder worker cycle failed")
        if not stopping:
            time.sleep(settings.REMINDER_WORKER_POLL_SECONDS)
    logger.info("Reminder worker stopped")


if __name__ == "__main__":
    main()
