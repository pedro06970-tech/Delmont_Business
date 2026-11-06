from app.models.user import UserRole


def setup_admin(user_factory, store_factory, login):
    user_factory(email="admin@example.com", role=UserRole.ADMIN)
    store = store_factory(name="Loja Modelo")
    _response, headers = login("admin@example.com")
    return store, headers


def test_create_edit_and_preview_template(client, user_factory, store_factory, login) -> None:
    store, headers = setup_admin(user_factory, store_factory, login)
    created = client.post(
        "/message-templates",
        headers=headers,
        json={
            "store_id": str(store.id),
            "name": "Lembrete",
            "content": "Olá, {{nome}}! Seu {{produto}} está na {{loja}}.",
        },
    )
    assert created.status_code == 201
    template_id = created.json()["id"]

    edited = client.patch(
        f"/message-templates/{template_id}",
        headers=headers,
        json={"name": "Lembrete editado"},
    )
    assert edited.status_code == 200

    preview = client.post(
        f"/message-templates/{template_id}/preview",
        headers=headers,
        json={"customer_name": "Maria", "product": "vestido"},
    )
    assert preview.status_code == 200
    assert preview.json()["rendered_content"] == "Olá, Maria! Seu vestido está na Loja Modelo."


def test_unknown_or_malformed_variables_are_rejected(
    client, user_factory, store_factory, login
) -> None:
    store, headers = setup_admin(user_factory, store_factory, login)
    for content in ("Olá, {{email}}", "Olá, {{ nome"):
        response = client.post(
            "/message-templates",
            headers=headers,
            json={"store_id": str(store.id), "name": content, "content": content},
        )
        assert response.status_code == 422


def test_preview_returns_untrusted_values_as_plain_data(
    client, user_factory, store_factory, login
) -> None:
    store, headers = setup_admin(user_factory, store_factory, login)
    template = client.post(
        "/message-templates",
        headers=headers,
        json={"store_id": str(store.id), "name": "Seguro", "content": "Olá, {{nome}}: {{produto}}"},
    ).json()
    preview = client.post(
        f"/message-templates/{template['id']}/preview",
        headers=headers,
        json={"customer_name": "<script>alert(1)</script>", "product": "<b>produto</b>"},
    )
    assert preview.status_code == 200
    assert preview.json()["rendered_content"] == (
        "Olá, <script>alert(1)</script>: <b>produto</b>"
    )


def test_inactive_template_cannot_be_previewed(client, user_factory, store_factory, login) -> None:
    store, headers = setup_admin(user_factory, store_factory, login)
    template = client.post(
        "/message-templates",
        headers=headers,
        json={
            "store_id": str(store.id),
            "name": "Inativo",
            "content": "Olá, {{nome}}",
            "is_active": False,
        },
    ).json()
    response = client.post(
        f"/message-templates/{template['id']}/preview", headers=headers, json={}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "inactive_template"


def test_templates_are_isolated_by_store(client, user_factory, store_factory, login) -> None:
    admin = user_factory(email="admin@example.com", role=UserRole.ADMIN)
    collaborator = user_factory(email="collab@example.com")
    allowed = store_factory(name="Permitida", users=[collaborator])
    denied = store_factory(name="Negada")
    _response, headers = login("admin@example.com")
    template = client.post(
        "/message-templates",
        headers=headers,
        json={"store_id": str(denied.id), "name": "Privado", "content": "Olá"},
    ).json()
    assert admin.id

    client.cookies.clear()
    login("collab@example.com")
    assert client.get(f"/message-templates?store_id={allowed.id}").status_code == 200
    assert client.get(f"/message-templates?store_id={denied.id}").status_code == 404
    assert client.get(f"/message-templates/{template['id']}").status_code == 404


def test_template_endpoints_require_authentication(client, store_factory) -> None:
    store = store_factory()
    assert client.get(f"/message-templates?store_id={store.id}").status_code == 401
