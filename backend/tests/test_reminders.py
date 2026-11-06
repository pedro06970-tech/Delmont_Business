from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.main import app
from app.models.user import UserRole


def future_iso(hours: int = 24) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).replace(microsecond=0).isoformat()


def setup_commercial(client, user_factory, store_factory, login):
    user_factory(email="admin@example.com", role=UserRole.ADMIN)
    store = store_factory(name="Loja Centro")
    response, headers = login("admin@example.com")
    assert response.status_code == 200
    customer = client.post(
        "/customers",
        headers=headers,
        json={"store_id": str(store.id), "name": "Maria", "phone": "+5511912345678"},
    ).json()
    consent = client.post(
        f"/customers/{customer['id']}/consent",
        headers=headers,
        json={"source": "Formulário na loja"},
    )
    assert consent.status_code == 200
    template = client.post(
        "/message-templates",
        headers=headers,
        json={
            "store_id": str(store.id),
            "name": "Retorno",
            "content": "Olá, {{nome}}! O {{produto}} está disponível na {{loja}}.",
        },
    ).json()
    return store, customer, template, headers


def reminder_payload(store, customer, template, *, product="Vestido", hours=24):
    return {
        "store_id": str(store.id),
        "customer_id": customer["id"],
        "message_template_id": template["id"],
        "product_interest": product,
        "scheduled_for": future_iso(hours),
    }


def test_create_list_get_and_edit_reminder_rerenders_message(
    client, user_factory, store_factory, login
) -> None:
    store, customer, template, headers = setup_commercial(
        client, user_factory, store_factory, login
    )
    created = client.post(
        "/reminders",
        headers=headers,
        json=reminder_payload(store, customer, template),
    )
    assert created.status_code == 201
    reminder = created.json()
    assert reminder["status"] == "pending"
    assert reminder["rendered_message"] == (
        "Olá, Maria! O Vestido está disponível na Loja Centro."
    )

    listed = client.get(f"/reminders?store_id={store.id}")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == reminder["id"]
    assert client.get(f"/reminders/{reminder['id']}").status_code == 200

    edited = client.patch(
        f"/reminders/{reminder['id']}",
        headers=headers,
        json={"product_interest": "Camisa", "scheduled_for": future_iso(48)},
    )
    assert edited.status_code == 200
    assert "Camisa" in edited.json()["rendered_message"]
    assert edited.json()["product_interest"] == "Camisa"


def test_create_requires_consent_active_customer_and_active_template(
    client, user_factory, store_factory, login
) -> None:
    store, customer, template, headers = setup_commercial(
        client, user_factory, store_factory, login
    )
    assert client.post(
        f"/customers/{customer['id']}/revoke-consent", headers=headers
    ).status_code == 200
    no_consent = client.post(
        "/reminders", headers=headers, json=reminder_payload(store, customer, template)
    )
    assert no_consent.status_code == 409
    assert no_consent.json()["error"]["code"] == "consent_required"

    assert client.post(
        f"/customers/{customer['id']}/consent",
        headers=headers,
        json={"source": "Renovado"},
    ).status_code == 200
    assert client.patch(
        f"/customers/{customer['id']}", headers=headers, json={"is_active": False}
    ).status_code == 200
    inactive_customer = client.post(
        "/reminders", headers=headers, json=reminder_payload(store, customer, template)
    )
    assert inactive_customer.json()["error"]["code"] == "inactive_customer"

    assert client.patch(
        f"/customers/{customer['id']}", headers=headers, json={"is_active": True}
    ).status_code == 200
    assert client.patch(
        f"/message-templates/{template['id']}", headers=headers, json={"is_active": False}
    ).status_code == 200
    inactive_template = client.post(
        "/reminders", headers=headers, json=reminder_payload(store, customer, template)
    )
    assert inactive_template.json()["error"]["code"] == "inactive_template"


def test_exact_pending_duplicate_is_rejected(
    client, user_factory, store_factory, login
) -> None:
    store, customer, template, headers = setup_commercial(
        client, user_factory, store_factory, login
    )
    payload = reminder_payload(store, customer, template)
    assert client.post("/reminders", headers=headers, json=payload).status_code == 201
    duplicate = client.post("/reminders", headers=headers, json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "duplicate_reminder"


def test_database_constraint_prevents_concurrent_duplicates(
    client, user_factory, store_factory, login
) -> None:
    store, customer, template, _headers = setup_commercial(
        client, user_factory, store_factory, login
    )
    payload = reminder_payload(store, customer, template)

    first = TestClient(app)
    second = TestClient(app)
    try:
        first_login = first.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "StrongPassword123!"},
        )
        second_login = second.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "StrongPassword123!"},
        )
        assert first_login.status_code == second_login.status_code == 200

        def create(test_client: TestClient) -> int:
            return test_client.post(
                "/reminders",
                headers={"X-CSRF-Token": test_client.cookies["delmont_csrf"]},
                json=payload,
            ).status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(create, (first, second)))
        assert sorted(statuses) == [201, 409]
    finally:
        first.close()
        second.close()


def test_cancel_is_idempotent_and_prevents_editing(
    client, user_factory, store_factory, login
) -> None:
    store, customer, template, headers = setup_commercial(
        client, user_factory, store_factory, login
    )
    reminder = client.post(
        "/reminders", headers=headers, json=reminder_payload(store, customer, template)
    ).json()
    first = client.post(f"/reminders/{reminder['id']}/cancel", headers=headers)
    second = client.post(f"/reminders/{reminder['id']}/cancel", headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json()["status"] == second.json()["status"] == "cancelled"
    assert first.json()["cancelled_at"] == second.json()["cancelled_at"]
    assert client.patch(
        f"/reminders/{reminder['id']}", headers=headers, json={"product_interest": "Outro"}
    ).status_code == 409


def test_completed_sale_cancels_product_reminders_idempotently(
    client, user_factory, store_factory, login
) -> None:
    store, customer, template, headers = setup_commercial(
        client, user_factory, store_factory, login
    )
    for hours in (24, 48):
        assert client.post(
            "/reminders",
            headers=headers,
            json=reminder_payload(store, customer, template, product="Vestido Azul", hours=hours),
        ).status_code == 201
    assert client.post(
        "/reminders",
        headers=headers,
        json=reminder_payload(store, customer, template, product="Sapato", hours=72),
    ).status_code == 201
    sale = {
        "store_id": str(store.id),
        "customer_id": customer["id"],
        "product_interest": "  vestido   azul ",
    }
    first = client.post("/reminders/cancel-product", headers=headers, json=sale)
    second = client.post("/reminders/cancel-product", headers=headers, json=sale)
    assert first.json()["cancelled_count"] == 2
    assert second.json()["cancelled_count"] == 0
    pending = client.get(f"/reminders?store_id={store.id}&status=pending").json()
    assert pending["total"] == 1
    assert pending["items"][0]["product_interest"] == "Sapato"


def test_reminders_are_isolated_between_stores(
    client, user_factory, store_factory, login
) -> None:
    store, customer, template, headers = setup_commercial(
        client, user_factory, store_factory, login
    )
    reminder = client.post(
        "/reminders", headers=headers, json=reminder_payload(store, customer, template)
    ).json()
    collaborator = user_factory(email="collab@example.com")
    allowed = store_factory(name="Permitida", users=[collaborator])
    client.cookies.clear()
    response, collab_headers = login("collab@example.com")
    assert response.status_code == 200
    assert client.get(f"/reminders?store_id={allowed.id}").status_code == 200
    assert client.get(f"/reminders?store_id={store.id}").status_code == 404
    assert client.get(f"/reminders/{reminder['id']}").status_code == 404
    assert client.post(
        f"/reminders/{reminder['id']}/cancel", headers=collab_headers
    ).status_code == 404


def test_reminders_require_authentication(client, store_factory) -> None:
    store = store_factory()
    assert client.get(f"/reminders?store_id={store.id}").status_code == 401
