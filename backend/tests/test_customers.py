from app.models.user import UserRole


def authenticated_admin(user_factory, login):
    user = user_factory(email="admin@example.com", role=UserRole.ADMIN)
    response, headers = login("admin@example.com")
    assert response.status_code == 200
    return user, headers


def test_create_and_edit_customer_normalizes_phone_without_consent(
    client, user_factory, store_factory, login
) -> None:
    _admin, headers = authenticated_admin(user_factory, login)
    store = store_factory(name="Centro")
    created = client.post(
        "/customers",
        headers=headers,
        json={
            "store_id": str(store.id),
            "name": "Maria Silva",
            "phone": "(11) 91234-5678",
            "notes": "Prefere contato à tarde",
        },
    )
    assert created.status_code == 201
    payload = created.json()
    assert payload["phone_e164"] == "+5511912345678"
    assert payload["has_consent"] is False
    assert payload["consented_at"] is None

    presumed = client.post(
        "/customers",
        headers=headers,
        json={
            "store_id": str(store.id),
            "name": "Consentimento presumido",
            "phone": "+5511988888888",
            "has_consent": True,
        },
    )
    assert presumed.status_code == 422

    edited = client.patch(
        f"/customers/{payload['id']}",
        headers=headers,
        json={"name": "Maria Souza", "is_active": False},
    )
    assert edited.status_code == 200
    assert edited.json()["name"] == "Maria Souza"
    assert edited.json()["is_active"] is False


def test_invalid_phone_is_rejected(client, user_factory, store_factory, login) -> None:
    _admin, headers = authenticated_admin(user_factory, login)
    store = store_factory()
    response = client.post(
        "/customers",
        headers=headers,
        json={"store_id": str(store.id), "name": "Telefone Ruim", "phone": "12345678"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_phone"


def test_phone_is_unique_per_store_but_allowed_in_another_store(
    client, user_factory, store_factory, login
) -> None:
    _admin, headers = authenticated_admin(user_factory, login)
    first_store = store_factory(name="Loja A")
    second_store = store_factory(name="Loja B")
    body = {"name": "Ana", "phone": "+55 21 99876-5432"}

    first = client.post(
        "/customers", headers=headers, json={**body, "store_id": str(first_store.id)}
    )
    assert first.status_code == 201
    duplicate = client.post(
        "/customers", headers=headers, json={**body, "store_id": str(first_store.id)}
    )
    assert duplicate.status_code == 409
    other_store = client.post(
        "/customers", headers=headers, json={**body, "store_id": str(second_store.id)}
    )
    assert other_store.status_code == 201


def test_customer_search_and_pagination(client, user_factory, store_factory, login) -> None:
    _admin, headers = authenticated_admin(user_factory, login)
    store = store_factory()
    customers = [
        ("Alice", "+5511911111111"),
        ("Beatriz", "+5511922222222"),
        ("Carla", "+5511933333333"),
    ]
    for name, phone in customers:
        assert client.post(
            "/customers",
            headers=headers,
            json={"store_id": str(store.id), "name": name, "phone": phone},
        ).status_code == 201

    page = client.get(f"/customers?store_id={store.id}&page=2&page_size=2")
    assert page.status_code == 200
    assert page.json()["total"] == 3
    assert page.json()["pages"] == 2
    assert [item["name"] for item in page.json()["items"]] == ["Carla"]

    search = client.get(f"/customers?store_id={store.id}&search=2222")
    assert [item["name"] for item in search.json()["items"]] == ["Beatriz"]


def test_customer_access_is_scoped_and_switching_store_changes_results(
    client, user_factory, store_factory, login
) -> None:
    admin, headers = authenticated_admin(user_factory, login)
    collaborator = user_factory(email="collab@example.com")
    allowed = store_factory(name="Permitida", users=[collaborator])
    denied = store_factory(name="Negada")
    first = client.post(
        "/customers",
        headers=headers,
        json={"store_id": str(allowed.id), "name": "Cliente A", "phone": "+5511944444444"},
    ).json()
    second = client.post(
        "/customers",
        headers=headers,
        json={"store_id": str(denied.id), "name": "Cliente B", "phone": "+5511955555555"},
    ).json()
    assert admin.id

    client.cookies.clear()
    login("collab@example.com")
    allowed_list = client.get(f"/customers?store_id={allowed.id}")
    assert [item["id"] for item in allowed_list.json()["items"]] == [first["id"]]
    assert client.get(f"/customers?store_id={denied.id}").status_code == 404
    assert client.get(f"/customers/{second['id']}").status_code == 404


def test_consent_grant_revoke_and_history(client, user_factory, store_factory, login) -> None:
    _admin, headers = authenticated_admin(user_factory, login)
    store = store_factory()
    customer = client.post(
        "/customers",
        headers=headers,
        json={"store_id": str(store.id), "name": "Consentimento", "phone": "+5511966666666"},
    ).json()

    granted = client.post(
        f"/customers/{customer['id']}/consent",
        headers=headers,
        json={"source": "Formulário assinado na loja"},
    )
    assert granted.status_code == 200
    assert granted.json()["has_consent"] is True
    assert granted.json()["consent_source"] == "Formulário assinado na loja"
    assert granted.json()["consent_history"][0]["action"] == "granted"

    revoked = client.post(f"/customers/{customer['id']}/revoke-consent", headers=headers)
    assert revoked.status_code == 200
    assert revoked.json()["has_consent"] is False
    assert revoked.json()["consent_revoked_at"] is not None
    assert [event["action"] for event in revoked.json()["consent_history"]] == [
        "granted",
        "revoked",
    ]


def test_customer_endpoints_require_authentication(client, store_factory) -> None:
    store = store_factory()
    assert client.get(f"/customers?store_id={store.id}").status_code == 401
    assert client.post(
        "/customers",
        json={"store_id": str(store.id), "name": "Sem acesso", "phone": "+5511977777777"},
    ).status_code == 401
