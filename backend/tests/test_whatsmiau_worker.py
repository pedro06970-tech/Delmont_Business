import json
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.integrations.whatsmiau import WhatsMiauClient
from app.models.commercial import (
    Customer,
    MessageTemplate,
    Reminder,
    ReminderDeliveryAttempt,
    WhatsMiauConfiguration,
)
from app.models.user import UserRole
from app.models.store import UserStore
from app.worker.reminders import ReminderWorker, recover_expired_claims


class MockWhatsMiauState:
    def __init__(self) -> None:
        self.connection_states = defaultdict(lambda: "open")
        self.send_modes: list[str] = []
        self.requests: list[dict] = []
        self.lock = threading.Lock()


@pytest.fixture
def whatsmiau_server():
    state = MockWhatsMiauState()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format, *_args):
            return

        def send_json(self, status, payload):
            encoded = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            try:
                self.wfile.write(encoded)
            except BrokenPipeError:
                pass

        def do_GET(self):
            instance = self.path.rsplit("/", 1)[-1]
            with state.lock:
                state.requests.append({"method": "GET", "path": self.path})
                connection_state = state.connection_states[instance]
            self.send_json(200, {"id": instance, "state": connection_state})

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            with state.lock:
                state.requests.append(
                    {
                        "method": "POST",
                        "path": self.path,
                        "body": body,
                        "apikey": self.headers.get("apikey"),
                    }
                )
                mode = state.send_modes.pop(0) if state.send_modes else "accepted"
                message_number = len(
                    [request for request in state.requests if request["method"] == "POST"]
                )
            if mode == "timeout":
                time.sleep(0.2)
                self.send_json(200, {"key": {"id": f"late-{message_number}"}})
            elif mode == "permanent":
                self.send_json(400, {"error": "invalid number"})
            elif mode == "temporary":
                self.send_json(429, {"error": "rate limited"})
            elif mode == "ambiguous":
                self.send_json(500, {"error": "server error"})
            else:
                self.send_json(
                    200,
                    {"key": {"id": f"msg-{message_number}"}, "status": "accepted"},
                )

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state, f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()


@pytest.fixture(autouse=True)
def worker_settings(monkeypatch):
    monkeypatch.setattr(settings, "REMINDER_DISPATCH_ENABLED", True)
    monkeypatch.setattr(settings, "REMINDER_WORKER_BATCH_SIZE", 10)
    monkeypatch.setattr(settings, "REMINDER_CLAIM_TTL_SECONDS", 10)
    monkeypatch.setattr(settings, "REMINDER_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(settings, "REMINDER_RETRY_BASE_SECONDS", 1)
    monkeypatch.setattr(settings, "REMINDER_INSTANCE_CONCURRENCY", 1)
    monkeypatch.setattr(settings, "REMINDER_MIN_INTERVAL_SECONDS", 0.0)
    monkeypatch.setenv("TEST_WHATSMIAU_KEY", "test-secret-key")


def setup_delivery(db, user_factory, store_factory, *, store_name="Centro", instance="store-1"):
    admin = user_factory(
        email=f"{instance}@example.com", role=UserRole.ADMIN
    )
    store = store_factory(name=store_name)
    customer = Customer(
        store_id=store.id,
        name="Maria",
        phone_e164="+5511912345678",
        is_active=True,
        has_consent=True,
        consented_at=datetime.now(UTC),
        consent_source="Loja",
        created_by_user_id=admin.id,
    )
    template = MessageTemplate(
        store_id=store.id,
        name="Retorno",
        content="Olá, {{nome}}",
        is_active=True,
        created_by_user_id=admin.id,
    )
    configuration = WhatsMiauConfiguration(
        store_id=store.id,
        instance_name=instance,
        credential_env_var="TEST_WHATSMIAU_KEY",
        is_enabled=True,
        dispatch_paused=False,
        connection_state="unknown",
    )
    db.add_all([customer, template, configuration])
    db.flush()
    db.commit()
    return admin, store, customer, template, configuration


def add_reminder(db, admin, store, customer, template, *, scheduled_for=None):
    reminder = Reminder(
        store_id=store.id,
        customer_id=customer.id,
        message_template_id=template.id,
        product_interest="Vestido",
        product_key="vestido",
        scheduled_for=scheduled_for or datetime.now(UTC) - timedelta(seconds=1),
        rendered_message="Olá, Maria! Seu vestido está disponível.",
        status="pending",
        execution_status="pending",
        created_by_user_id=admin.id,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


def fresh(db, model, object_id):
    db.expire_all()
    return db.get(model, object_id)


def test_due_reminder_is_sent_and_future_reminder_waits(
    db, user_factory, store_factory, whatsmiau_server, caplog
) -> None:
    state, url = whatsmiau_server
    admin, store, customer, template, _config = setup_delivery(
        db, user_factory, store_factory
    )
    due = add_reminder(db, admin, store, customer, template)
    future = add_reminder(
        db,
        admin,
        store,
        customer,
        template,
        scheduled_for=datetime.now(UTC) + timedelta(hours=1),
    )
    processed = ReminderWorker(WhatsMiauClient(base_url=url)).run_once()
    assert processed == 1
    assert fresh(db, Reminder, due.id).execution_status == "sent"
    assert fresh(db, Reminder, due.id).status == "completed"
    assert fresh(db, Reminder, future.id).execution_status == "pending"
    posts = [request for request in state.requests if request["method"] == "POST"]
    assert posts[0]["body"] == {
        "number": "5511912345678",
        "text": "Olá, Maria! Seu vestido está disponível.",
    }
    assert posts[0]["apikey"] == "test-secret-key"
    assert "test-secret-key" not in caplog.text


@pytest.mark.parametrize(
    ("change", "expected_error"),
    [
        ("no_consent", "consentimento"),
        ("inactive_customer", "inativo"),
        ("cancelled", None),
    ],
)
def test_invalid_customer_or_cancelled_reminder_is_not_sent(
    db, user_factory, store_factory, whatsmiau_server, change, expected_error
) -> None:
    state, url = whatsmiau_server
    admin, store, customer, template, _config = setup_delivery(
        db, user_factory, store_factory
    )
    reminder = add_reminder(db, admin, store, customer, template)
    if change == "no_consent":
        customer.has_consent = False
    elif change == "inactive_customer":
        customer.is_active = False
    else:
        reminder.status = "cancelled"
    db.commit()
    ReminderWorker(WhatsMiauClient(base_url=url)).run_once()
    result = fresh(db, Reminder, reminder.id)
    if expected_error:
        assert result.execution_status == "failed"
        assert expected_error in result.failure_reason
    else:
        assert result.status == "cancelled"
    assert not [request for request in state.requests if request["method"] == "POST"]


def test_consent_revoked_after_claim_prevents_send(
    db, user_factory, store_factory, whatsmiau_server
) -> None:
    from app.worker.reminders import claim_due_reminders

    state, url = whatsmiau_server
    admin, store, customer, template, _config = setup_delivery(
        db, user_factory, store_factory
    )
    reminder = add_reminder(db, admin, store, customer, template)
    now = datetime.now(UTC)
    claims = claim_due_reminders(db, now, 1)
    customer.has_consent = False
    db.commit()
    ReminderWorker(WhatsMiauClient(base_url=url)).process_claim(*claims[0], now=now)
    assert fresh(db, Reminder, reminder.id).execution_status == "failed"
    assert not [request for request in state.requests if request["method"] == "POST"]


def test_paused_store_and_disconnected_instance_wait_without_send(
    db, user_factory, store_factory, whatsmiau_server
) -> None:
    state, url = whatsmiau_server
    admin, store, customer, template, configuration = setup_delivery(
        db, user_factory, store_factory
    )
    paused = add_reminder(db, admin, store, customer, template)
    configuration.dispatch_paused = True
    db.commit()
    ReminderWorker(WhatsMiauClient(base_url=url)).run_once()
    assert fresh(db, Reminder, paused.id).execution_status == "pending"

    configuration = fresh(db, WhatsMiauConfiguration, configuration.id)
    configuration.dispatch_paused = False
    state.connection_states[configuration.instance_name] = "closed"
    db.commit()
    ReminderWorker(WhatsMiauClient(base_url=url)).run_once(
        now=datetime.now(UTC) + timedelta(seconds=2)
    )
    assert fresh(db, Reminder, paused.id).execution_status == "retry_wait"
    assert not [request for request in state.requests if request["method"] == "POST"]


@pytest.mark.parametrize(
    ("mode", "execution", "commercial", "attempt_status"),
    [
        ("accepted", "sent", "completed", "accepted"),
        ("permanent", "failed", "failed", "failed"),
        ("ambiguous", "uncertain", "pending", "uncertain"),
        ("timeout", "uncertain", "pending", "uncertain"),
    ],
)
def test_provider_outcomes_are_persisted_without_unsafe_retry(
    db,
    user_factory,
    store_factory,
    whatsmiau_server,
    mode,
    execution,
    commercial,
    attempt_status,
) -> None:
    state, url = whatsmiau_server
    state.send_modes.append(mode)
    admin, store, customer, template, _config = setup_delivery(
        db, user_factory, store_factory
    )
    reminder = add_reminder(db, admin, store, customer, template)
    worker = ReminderWorker(WhatsMiauClient(base_url=url, timeout=0.05))
    worker.run_once()
    result = fresh(db, Reminder, reminder.id)
    attempt = db.scalar(
        select(ReminderDeliveryAttempt).where(
            ReminderDeliveryAttempt.reminder_id == reminder.id
        )
    )
    assert result.execution_status == execution
    assert result.status == commercial
    assert attempt.status == attempt_status
    assert attempt.finished_at is not None
    if execution == "uncertain":
        worker.run_once(now=datetime.now(UTC) + timedelta(hours=1))
        posts = [request for request in state.requests if request["method"] == "POST"]
        assert len(posts) == 1
        assert worker.reconcile_uncertain() == 0


def test_safe_temporary_failure_retries_with_backoff(
    db, user_factory, store_factory, whatsmiau_server
) -> None:
    state, url = whatsmiau_server
    state.send_modes.extend(["temporary", "accepted"])
    admin, store, customer, template, _config = setup_delivery(
        db, user_factory, store_factory
    )
    reminder = add_reminder(db, admin, store, customer, template)
    worker = ReminderWorker(WhatsMiauClient(base_url=url))
    start = datetime.now(UTC)
    worker.run_once(now=start)
    waiting = fresh(db, Reminder, reminder.id)
    assert waiting.execution_status == "retry_wait"
    assert waiting.next_attempt_at == start + timedelta(seconds=1)
    worker.run_once(now=start + timedelta(seconds=2))
    assert fresh(db, Reminder, reminder.id).execution_status == "sent"
    attempts = list(
        db.scalars(
            select(ReminderDeliveryAttempt)
            .where(ReminderDeliveryAttempt.reminder_id == reminder.id)
            .order_by(ReminderDeliveryAttempt.attempt_number)
        )
    )
    assert [attempt.status for attempt in attempts] == ["retry_wait", "accepted"]


def test_expired_claim_recovery_distinguishes_claimed_from_sending(
    db, user_factory, store_factory
) -> None:
    admin, store, customer, template, configuration = setup_delivery(
        db, user_factory, store_factory
    )
    claimed = add_reminder(db, admin, store, customer, template)
    sending = add_reminder(db, admin, store, customer, template)
    expired = datetime.now(UTC) - timedelta(seconds=1)
    claimed.execution_status = "claimed"
    claimed.claim_token = __import__("uuid").uuid4()
    claimed.lease_expires_at = expired
    sending.execution_status = "sending"
    sending.claim_token = __import__("uuid").uuid4()
    sending.lease_expires_at = expired
    sending.attempt_count = 1
    db.add(
        ReminderDeliveryAttempt(
            reminder_id=sending.id,
            store_id=store.id,
            configuration_id=configuration.id,
            attempt_number=1,
            status="started",
        )
    )
    db.commit()
    released, uncertain = recover_expired_claims(db, datetime.now(UTC))
    assert (released, uncertain) == (1, 1)
    assert fresh(db, Reminder, claimed.id).execution_status == "pending"
    assert fresh(db, Reminder, sending.id).execution_status == "uncertain"


def test_two_workers_do_not_send_same_reminder_twice(
    db, user_factory, store_factory, whatsmiau_server
) -> None:
    state, url = whatsmiau_server
    admin, store, customer, template, _config = setup_delivery(
        db, user_factory, store_factory
    )
    reminder = add_reminder(db, admin, store, customer, template)
    workers = [
        ReminderWorker(WhatsMiauClient(base_url=url)),
        ReminderWorker(WhatsMiauClient(base_url=url)),
    ]
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda worker: worker.run_once(), workers))
    assert fresh(db, Reminder, reminder.id).execution_status == "sent"
    assert len([request for request in state.requests if request["method"] == "POST"]) == 1


def test_instance_concurrency_and_minimum_interval_limit_batch(
    db, user_factory, store_factory, whatsmiau_server, monkeypatch
) -> None:
    state, url = whatsmiau_server
    monkeypatch.setattr(settings, "REMINDER_MIN_INTERVAL_SECONDS", 60.0)
    admin, store, customer, template, _config = setup_delivery(
        db, user_factory, store_factory
    )
    reminders = [
        add_reminder(db, admin, store, customer, template),
        add_reminder(db, admin, store, customer, template),
    ]
    ReminderWorker(WhatsMiauClient(base_url=url)).run_once()
    results = [fresh(db, Reminder, reminder.id).execution_status for reminder in reminders]
    assert sorted(results) == ["retry_wait", "sent"]
    assert len([request for request in state.requests if request["method"] == "POST"]) == 1


def test_store_isolation_uses_each_instance_and_credential(
    db, user_factory, store_factory, whatsmiau_server, monkeypatch
) -> None:
    state, url = whatsmiau_server
    first = setup_delivery(db, user_factory, store_factory, store_name="A", instance="instance-a")
    second = setup_delivery(db, user_factory, store_factory, store_name="B", instance="instance-b")
    monkeypatch.setenv("SECOND_STORE_KEY", "second-secret")
    second[4].credential_env_var = "SECOND_STORE_KEY"
    db.commit()
    add_reminder(db, *first[:4])
    add_reminder(db, *second[:4])
    ReminderWorker(WhatsMiauClient(base_url=url)).run_once()
    posts = [request for request in state.requests if request["method"] == "POST"]
    assert {request["path"].rsplit("/", 1)[-1] for request in posts} == {
        "instance-a",
        "instance-b",
    }
    assert {request["apikey"] for request in posts} == {
        "test-secret-key",
        "second-secret",
    }


def test_missing_credential_and_http_communication_failure_are_safe(
    db, user_factory, store_factory, monkeypatch
) -> None:
    admin, store, customer, template, configuration = setup_delivery(
        db, user_factory, store_factory
    )
    missing = add_reminder(db, admin, store, customer, template)
    monkeypatch.delenv("TEST_WHATSMIAU_KEY")
    ReminderWorker(WhatsMiauClient(base_url="http://127.0.0.1:1", timeout=0.05)).run_once()
    assert fresh(db, Reminder, missing.id).execution_status == "failed"

    monkeypatch.setenv("TEST_WHATSMIAU_KEY", "secret")
    configuration = fresh(db, WhatsMiauConfiguration, configuration.id)
    second = add_reminder(db, admin, store, customer, template)
    ReminderWorker(WhatsMiauClient(base_url="http://127.0.0.1:1", timeout=0.05)).run_once(
        now=datetime.now(UTC) + timedelta(seconds=2)
    )
    assert fresh(db, Reminder, second.id).execution_status == "retry_wait"


def test_global_dispatch_switch_stops_claiming(
    db, user_factory, store_factory, whatsmiau_server, monkeypatch
) -> None:
    state, url = whatsmiau_server
    admin, store, customer, template, _config = setup_delivery(
        db, user_factory, store_factory
    )
    reminder = add_reminder(db, admin, store, customer, template)
    monkeypatch.setattr(settings, "REMINDER_DISPATCH_ENABLED", False)
    assert ReminderWorker(WhatsMiauClient(base_url=url)).run_once() == 0
    assert fresh(db, Reminder, reminder.id).execution_status == "pending"
    assert not state.requests


def test_admin_configuration_hides_secret_reference_and_collaborator_is_forbidden(
    client, user_factory, store_factory, login, monkeypatch, whatsmiau_server
) -> None:
    _state, url = whatsmiau_server
    monkeypatch.setattr(settings, "WHATSMIAU_BASE_URL", url)
    monkeypatch.setenv("PRIVATE_STORE_KEY", "never-return-this-secret")
    user_factory(email="admin@example.com", role=UserRole.ADMIN)
    collaborator = user_factory(email="collab@example.com")
    store = store_factory(users=[collaborator])
    _response, headers = login("admin@example.com")
    configured = client.put(
        f"/whatsmiau/configurations/{store.id}",
        headers=headers,
        json={
            "instance_name": "loja-centro",
            "credential_env_var": "PRIVATE_STORE_KEY",
        },
    )
    assert configured.status_code == 200
    body = configured.json()
    assert body["credential_configured"] is True
    assert "credential_env_var" not in body
    assert "never-return-this-secret" not in configured.text
    checked = client.post(
        f"/whatsmiau/configurations/{store.id}/check", headers=headers
    )
    assert checked.status_code == 200
    assert checked.json()["connection_state"] == "open"
    assert client.post(
        f"/whatsmiau/configurations/{store.id}/pause", headers=headers
    ).json()["dispatch_paused"] is True

    client.cookies.clear()
    login("collab@example.com")
    assert client.get(f"/whatsmiau/configurations/{store.id}").status_code == 403


def test_full_flow_records_accepted_delivered_and_read_idempotently(
    client, db, user_factory, store_factory, whatsmiau_server, monkeypatch
) -> None:
    _state, url = whatsmiau_server
    monkeypatch.setenv("TEST_WEBHOOK_SECRET", "webhook-test-secret")
    admin, store, customer, template, configuration = setup_delivery(
        db, user_factory, store_factory
    )
    configuration.webhook_secret_env_var = "TEST_WEBHOOK_SECRET"
    db.commit()
    reminder = add_reminder(db, admin, store, customer, template)
    ReminderWorker(WhatsMiauClient(base_url=url)).run_once()
    accepted = fresh(db, Reminder, reminder.id)
    assert accepted.provider_status == "accepted"
    assert accepted.delivered_at is None
    message_id = accepted.provider_message_id

    payload = {
        "event": "messages.update",
        "instance": configuration.instance_name,
        "data": {"messageId": message_id, "status": "DELIVERY_ACK"},
    }
    unauthorized = client.post(f"/webhooks/whatsmiau/{store.id}", json=payload)
    assert unauthorized.status_code == 401
    delivered = client.post(
        f"/webhooks/whatsmiau/{store.id}",
        headers={"X-Delmont-Webhook-Secret": "webhook-test-secret"},
        json=payload,
    )
    assert delivered.status_code == 200
    assert delivered.json()["processed"] is True
    delivered_reminder = fresh(db, Reminder, reminder.id)
    assert delivered_reminder.provider_status == "delivered"
    assert delivered_reminder.delivered_at is not None
    delivered_at = delivered_reminder.delivered_at

    payload["data"]["status"] = "READ"
    for _ in range(2):
        assert client.post(
            f"/webhooks/whatsmiau/{store.id}",
            headers={"X-Delmont-Webhook-Secret": "webhook-test-secret"},
            json=payload,
        ).status_code == 200
    read_reminder = fresh(db, Reminder, reminder.id)
    assert read_reminder.provider_status == "read"
    assert read_reminder.delivered_at == delivered_at
    assert read_reminder.read_at is not None


def test_homologation_mode_only_sends_to_explicitly_authorized_number(
    db, user_factory, store_factory, whatsmiau_server, monkeypatch
) -> None:
    state, url = whatsmiau_server
    monkeypatch.setattr(settings, "REMINDER_HOMOLOGATION_ONLY", True)
    admin, store, customer, template, configuration = setup_delivery(
        db, user_factory, store_factory
    )
    reminder = add_reminder(db, admin, store, customer, template)
    configuration.homologation_phone_e164 = "+5511999999999"
    configuration.homologation_authorized_at = datetime.now(UTC)
    db.commit()
    worker = ReminderWorker(WhatsMiauClient(base_url=url))
    start = datetime.now(UTC)
    worker.run_once(now=start)
    blocked = fresh(db, Reminder, reminder.id)
    assert blocked.execution_status == "pending"
    assert "não autorizado" in blocked.last_transport_error
    assert not [request for request in state.requests if request["method"] == "POST"]

    configuration = fresh(db, WhatsMiauConfiguration, configuration.id)
    configuration.homologation_phone_e164 = customer.phone_e164
    db.commit()
    worker.run_once(now=start + timedelta(seconds=2))
    assert fresh(db, Reminder, reminder.id).execution_status == "sent"


def test_operational_readiness_can_be_checked_by_authorized_collaborator(
    client,
    db,
    user_factory,
    store_factory,
    login,
    whatsmiau_server,
    monkeypatch,
) -> None:
    _state, url = whatsmiau_server
    monkeypatch.setattr(settings, "WHATSMIAU_BASE_URL", url)
    collaborator = user_factory(email="collab@example.com")
    allowed = store_factory(name="Permitida", users=[collaborator])
    denied = store_factory(name="Negada")
    configuration = WhatsMiauConfiguration(
        store_id=allowed.id,
        instance_name="allowed-instance",
        credential_env_var="TEST_WHATSMIAU_KEY",
        is_enabled=True,
        dispatch_paused=False,
        connection_state="unknown",
    )
    db.add(configuration)
    db.commit()
    _response, headers = login("collab@example.com")
    readiness = client.get(f"/whatsmiau/readiness/{allowed.id}")
    assert readiness.status_code == 200
    assert readiness.json()["ready_to_schedule"] is False
    checked = client.post(
        f"/whatsmiau/readiness/{allowed.id}/check", headers=headers
    )
    assert checked.status_code == 200
    assert checked.json()["ready_to_schedule"] is True
    assert client.get(f"/whatsmiau/readiness/{denied.id}").status_code == 404


def test_reconnected_instance_sends_once_and_cancel_after_claim_stops_send(
    db, user_factory, store_factory, whatsmiau_server
) -> None:
    from app.worker.reminders import claim_due_reminders

    state, url = whatsmiau_server
    admin, store, customer, template, configuration = setup_delivery(
        db, user_factory, store_factory
    )
    reconnecting = add_reminder(db, admin, store, customer, template)
    state.connection_states[configuration.instance_name] = "closed"
    worker = ReminderWorker(WhatsMiauClient(base_url=url))
    start = datetime.now(UTC)
    worker.run_once(now=start)
    assert fresh(db, Reminder, reconnecting.id).execution_status == "retry_wait"
    state.connection_states[configuration.instance_name] = "open"
    worker.run_once(now=start + timedelta(seconds=2))
    assert fresh(db, Reminder, reconnecting.id).execution_status == "sent"

    cancelled = add_reminder(db, admin, store, customer, template)
    claims = claim_due_reminders(db, start + timedelta(seconds=3), 1)
    cancelled = fresh(db, Reminder, cancelled.id)
    cancelled.status = "cancelled"
    db.commit()
    worker.process_claim(*claims[0], now=start + timedelta(seconds=3))
    assert len([request for request in state.requests if request["method"] == "POST"]) == 1


def test_reminder_attempt_history_respects_store_scope(
    client, db, user_factory, store_factory, login, whatsmiau_server
) -> None:
    _state, url = whatsmiau_server
    collaborator = user_factory(email="collab@example.com")
    admin, store, customer, template, _configuration = setup_delivery(
        db, user_factory, store_factory, store_name="Histórico", instance="history-instance"
    )
    db.add(UserStore(user_id=collaborator.id, store_id=store.id))
    db.commit()
    reminder = add_reminder(db, admin, store, customer, template)
    ReminderWorker(WhatsMiauClient(base_url=url)).run_once()
    _response, _headers = login("collab@example.com")
    history = client.get(f"/reminders/{reminder.id}/attempts")
    assert history.status_code == 200
    assert history.json()[0]["status"] == "accepted"

    other_admin, other_store, other_customer, other_template, _other_config = setup_delivery(
        db, user_factory, store_factory, store_name="Outra", instance="other-instance"
    )
    other = add_reminder(db, other_admin, other_store, other_customer, other_template)
    assert client.get(f"/reminders/{other.id}/attempts").status_code == 404
