from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import app
from app.models.commercial import Customer, Reminder, SalesOpportunity, SalesOpportunityEvent
from app.models.user import UserRole


def login_client(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"email": email, "password": "StrongPassword123!"},
    )
    assert response.status_code == 200
    return {"X-CSRF-Token": client.cookies.get("delmont_csrf")}


def create_customer(client, headers, store_id, *, name="Cliente", phone="85999991111"):
    response = client.post(
        "/customers",
        headers=headers,
        json={"store_id": str(store_id), "name": name, "phone": phone},
    )
    assert response.status_code == 201, response.text
    return response.json()


def grant_consent(client, headers, customer_id):
    response = client.post(
        f"/customers/{customer_id}/consent",
        headers=headers,
        json={"source": "Teste autorizado"},
    )
    assert response.status_code == 200, response.text


def create_template(client, headers, store_id):
    response = client.post(
        "/message-templates",
        headers=headers,
        json={
            "store_id": str(store_id),
            "name": "Retorno comercial",
            "content": "Olá {{nome}}, novidade sobre {{produto}} na {{loja}}.",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_opportunity(client, headers, store_id, customer_id, product):
    return client.post(
        "/sales-opportunities",
        headers=headers,
        json={
            "store_id": str(store_id),
            "customer_id": customer_id,
            "product_name": product,
        },
    )


def create_reminder(
    client, headers, store_id, customer_id, template_id, product, opportunity_id=None
):
    payload = {
        "store_id": str(store_id),
        "customer_id": customer_id,
        "message_template_id": template_id,
        "product_interest": product,
        "scheduled_for": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
    }
    if opportunity_id:
        payload["opportunity_id"] = opportunity_id
    response = client.post("/reminders", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def setup_admin(client, user_factory, store_factory, login):
    admin = user_factory(email="admin@example.com", role=UserRole.ADMIN)
    store = store_factory()
    response, headers = login(admin.email)
    assert response.status_code == 200
    customer = create_customer(client, headers, store.id)
    return admin, store, customer, headers


def test_create_multiple_opportunities_and_reject_duplicate_open(
    client, user_factory, store_factory, login
):
    _admin, store, customer, headers = setup_admin(
        client, user_factory, store_factory, login
    )
    first = create_opportunity(client, headers, store.id, customer["id"], "Vestido Azul")
    second = create_opportunity(client, headers, store.id, customer["id"], "Sapato")
    duplicate = create_opportunity(
        client, headers, store.id, customer["id"], "  vestido   azul "
    )
    assert first.status_code == second.status_code == 201
    assert duplicate.status_code == 409
    assert first.json()["events"][0]["new_status"] == "open"
    updated = client.patch(
        f"/sales-opportunities/{first.json()['id']}",
        headers=headers,
        json={"product_name": "Vestido Verde"},
    )
    assert updated.status_code == 200
    assert updated.json()["product_name"] == "Vestido Verde"
    listed = client.get(f"/sales-opportunities?store_id={store.id}")
    assert listed.status_code == 200
    assert listed.json()["total"] == 2
    assert client.get(
        f"/sales-opportunities?store_id={store.id}&status=won"
    ).json()["total"] == 0


def test_store_isolation_and_authorization(client, user_factory, store_factory, login):
    owner = user_factory(email="owner@example.com")
    outsider = user_factory(email="outsider@example.com")
    store = store_factory(users=[owner])
    other_store = store_factory(name="Outra", users=[outsider])
    _response, owner_headers = login(owner.email)
    customer = create_customer(client, owner_headers, store.id)
    opportunity = create_opportunity(
        client, owner_headers, store.id, customer["id"], "Bolsa"
    ).json()

    client.cookies.clear()
    _response, outsider_headers = login(outsider.email)
    assert client.get(f"/sales-opportunities?store_id={store.id}").status_code == 404
    assert client.get(f"/sales-opportunities/{opportunity['id']}").status_code == 404
    assert client.patch(
        f"/sales-opportunities/{opportunity['id']}",
        headers=outsider_headers,
        json={"product_name": "Bolsa nova"},
    ).status_code == 404
    assert client.post(
        f"/sales-opportunities/{opportunity['id']}/close",
        headers=outsider_headers,
        json={"status": "won"},
    ).status_code == 404
    assert client.get(f"/sales-opportunities?store_id={other_store.id}").status_code == 200


def test_close_won_cancels_only_related_reminders_and_preserves_legacy(
    client, db, user_factory, store_factory, login
):
    _admin, store, customer, headers = setup_admin(
        client, user_factory, store_factory, login
    )
    grant_consent(client, headers, customer["id"])
    template = create_template(client, headers, store.id)
    dress = create_opportunity(
        client, headers, store.id, customer["id"], "Vestido"
    ).json()
    shoes = create_opportunity(
        client, headers, store.id, customer["id"], "Sapato"
    ).json()
    dress_reminder = create_reminder(
        client,
        headers,
        store.id,
        customer["id"],
        template["id"],
        "Vestido",
        dress["id"],
    )
    shoes_reminder = create_reminder(
        client,
        headers,
        store.id,
        customer["id"],
        template["id"],
        "Sapato",
        shoes["id"],
    )
    legacy = create_reminder(
        client, headers, store.id, customer["id"], template["id"], "Cinto"
    )
    assert client.patch(
        f"/sales-opportunities/{dress['id']}",
        headers=headers,
        json={"product_name": "Vestido novo"},
    ).status_code == 409
    db.execute(
        Reminder.__table__.update()
        .where(Reminder.id == dress_reminder["id"])
        .values(execution_status="claimed", claim_token=uuid.uuid4(), claimed_at=datetime.now(UTC))
    )
    db.commit()

    closed = client.post(
        f"/sales-opportunities/{dress['id']}/close",
        headers=headers,
        json={"status": "won"},
    )
    repeated = client.post(
        f"/sales-opportunities/{dress['id']}/close",
        headers=headers,
        json={"status": "won"},
    )
    assert closed.status_code == repeated.status_code == 200
    assert closed.json()["status"] == "won"
    assert len(repeated.json()["events"]) == 2
    assert client.get(f"/reminders/{dress_reminder['id']}").json()["status"] == "cancelled"
    db.expire_all()
    cancelled = db.get(Reminder, dress_reminder["id"])
    assert cancelled.execution_status == "pending"
    assert cancelled.claim_token is None
    assert client.get(f"/reminders/{shoes_reminder['id']}").json()["status"] == "pending"
    legacy_result = client.get(f"/reminders/{legacy['id']}").json()
    assert legacy_result["status"] == "pending"
    assert legacy_result["opportunity_id"] is None
    rejected = client.post(
        "/reminders",
        headers=headers,
        json={
            "store_id": str(store.id),
            "customer_id": customer["id"],
            "message_template_id": template["id"],
            "product_interest": "Vestido",
            "opportunity_id": dress["id"],
            "scheduled_for": (datetime.now(UTC) + timedelta(days=4)).isoformat(),
        },
    )
    assert rejected.status_code == 409


def test_close_lost_records_reason_and_cancels_related_reminder(
    client, user_factory, store_factory, login
):
    _admin, store, customer, headers = setup_admin(
        client, user_factory, store_factory, login
    )
    grant_consent(client, headers, customer["id"])
    template = create_template(client, headers, store.id)
    opportunity = create_opportunity(
        client, headers, store.id, customer["id"], "Jaqueta"
    ).json()
    reminder = create_reminder(
        client,
        headers,
        store.id,
        customer["id"],
        template["id"],
        "Jaqueta",
        opportunity["id"],
    )
    response = client.post(
        f"/sales-opportunities/{opportunity['id']}/close",
        headers=headers,
        json={"status": "lost", "lost_reason": "Cliente desistiu"},
    )
    assert response.status_code == 200
    assert response.json()["lost_reason"] == "Cliente desistiu"
    assert response.json()["events"][-1]["new_status"] == "lost"
    assert client.get(f"/reminders/{reminder['id']}").json()["status"] == "cancelled"


def test_concurrent_close_is_idempotent(
    client, db, user_factory, store_factory, login
):
    admin, store, customer, headers = setup_admin(
        client, user_factory, store_factory, login
    )
    opportunity = create_opportunity(
        client, headers, store.id, customer["id"], "Blusa"
    ).json()

    def close_once():
        with TestClient(app) as concurrent_client:
            concurrent_headers = login_client(concurrent_client, admin.email)
            return concurrent_client.post(
                f"/sales-opportunities/{opportunity['id']}/close",
                headers=concurrent_headers,
                json={"status": "won"},
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(lambda _value: close_once(), range(2)))
    assert statuses == [200, 200]
    event_count = db.scalar(
        select(func.count(SalesOpportunityEvent.id)).where(
            SalesOpportunityEvent.opportunity_id == opportunity["id"]
        )
    )
    assert event_count == 2


def test_concurrent_duplicate_creation_keeps_single_open_opportunity(
    client, db, user_factory, store_factory, login
):
    admin, store, customer, _headers = setup_admin(
        client, user_factory, store_factory, login
    )

    def create_once():
        with TestClient(app) as concurrent_client:
            concurrent_headers = login_client(concurrent_client, admin.email)
            return create_opportunity(
                concurrent_client,
                concurrent_headers,
                store.id,
                customer["id"],
                "Produto concorrente",
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = sorted(executor.map(lambda _value: create_once(), range(2)))
    assert statuses == [201, 409]
    db.expire_all()
    count = db.scalar(
        select(func.count(SalesOpportunity.id)).where(
            SalesOpportunity.store_id == store.id,
            SalesOpportunity.customer_id == customer["id"],
            SalesOpportunity.status == "open",
        )
    )
    assert count == 1


def test_dashboard_metrics_period_collaborator_and_timezone(
    client, db, user_factory, store_factory, login
):
    first_user = user_factory(email="first@example.com")
    second_user = user_factory(email="second@example.com")
    store = store_factory(users=[first_user, second_user])
    _response, first_headers = login(first_user.email)
    first_customer = create_customer(
        client, first_headers, store.id, name="Dentro", phone="85999991111"
    )
    grant_consent(client, first_headers, first_customer["id"])
    template = create_template(client, first_headers, store.id)
    won = create_opportunity(
        client, first_headers, store.id, first_customer["id"], "Produto A"
    ).json()
    open_at_period_end = create_opportunity(
        client, first_headers, store.id, first_customer["id"], "Produto futuro"
    ).json()
    reminder = create_reminder(
        client,
        first_headers,
        store.id,
        first_customer["id"],
        template["id"],
        "Produto A",
        won["id"],
    )
    client.post(
        f"/sales-opportunities/{won['id']}/close",
        headers=first_headers,
        json={"status": "won"},
    )
    client.post(
        f"/sales-opportunities/{open_at_period_end['id']}/close",
        headers=first_headers,
        json={"status": "won"},
    )

    client.cookies.clear()
    _response, second_headers = login(second_user.email)
    second_customer = create_customer(
        client, second_headers, store.id, name="Fora", phone="85999992222"
    )
    lost = create_opportunity(
        client, second_headers, store.id, second_customer["id"], "Produto B"
    ).json()
    client.post(
        f"/sales-opportunities/{lost['id']}/close",
        headers=second_headers,
        json={"status": "lost", "lost_reason": "Sem interesse"},
    )

    inside = datetime(2026, 11, 1, 3, 0, tzinfo=UTC)
    outside = inside - timedelta(seconds=1)
    db.execute(
        Customer.__table__.update()
        .where(Customer.id == first_customer["id"])
        .values(created_at=inside)
    )
    db.execute(
        Customer.__table__.update()
        .where(Customer.id == second_customer["id"])
        .values(created_at=outside)
    )
    db.execute(
        SalesOpportunity.__table__.update()
        .where(SalesOpportunity.id.in_([won["id"], lost["id"]]))
        .values(created_at=inside, closed_at=inside + timedelta(hours=1))
    )
    db.execute(
        SalesOpportunity.__table__.update()
        .where(SalesOpportunity.id == open_at_period_end["id"])
        .values(created_at=inside, closed_at=datetime(2026, 11, 2, 4, 0, tzinfo=UTC))
    )
    db.execute(
        Reminder.__table__.update()
        .where(Reminder.id == reminder["id"])
        .values(created_at=inside, accepted_at=inside + timedelta(hours=2))
    )
    db.commit()

    dashboard = client.get(
        f"/commercial/dashboard?store_id={store.id}&date_from=2026-11-01&date_to=2026-11-01"
    )
    assert dashboard.status_code == 200, dashboard.text
    body = dashboard.json()
    assert body["period"]["timezone"] == "America/Fortaleza"
    assert body["metrics"] == {
        "distinct_leads": 1,
        "open_opportunities": 1,
        "scheduled_reminders": 1,
        "accepted_messages": 1,
        "won_opportunities": 1,
        "lost_opportunities": 1,
        "conversion_rate": 50.0,
        "conversion_has_basis": True,
        "conversion_definition": body["metrics"]["conversion_definition"],
    }
    assert body["reminder_evolution"] == [{"date": "2026-11-01", "reminders": 1}]
    assert len(body["collaborator_performance"]) == 2

    filtered = client.get(
        f"/commercial/dashboard?store_id={store.id}&date_from=2026-11-01&date_to=2026-11-01"
        f"&created_by_user_id={first_user.id}"
    ).json()
    assert filtered["metrics"]["won_opportunities"] == 1
    assert filtered["metrics"]["lost_opportunities"] == 0
    assert filtered["metrics"]["conversion_rate"] == 100.0
    assert len(filtered["collaborator_performance"]) == 1


def test_dashboard_zero_conversion_has_no_basis(
    client, user_factory, store_factory, login
):
    _admin, store, _customer, _headers = setup_admin(
        client, user_factory, store_factory, login
    )
    body = client.get(f"/commercial/dashboard?store_id={store.id}").json()
    assert body["metrics"]["conversion_rate"] == 0
    assert body["metrics"]["conversion_has_basis"] is False
