from app.models.user import UserRole


def test_admin_access_allowed_and_collaborator_denied(client, user_factory, login) -> None:
    user_factory(email="admin@example.com", role=UserRole.ADMIN)
    response, _headers = login("admin@example.com")
    assert response.status_code == 200
    assert client.get("/users").status_code == 200

    client.cookies.clear()
    user_factory(email="collab@example.com")
    login("collab@example.com")
    denied = client.get("/users")
    assert denied.status_code == 403


def test_admin_can_create_edit_and_cannot_duplicate_users(client, user_factory, login) -> None:
    user_factory(email="admin@example.com", role=UserRole.ADMIN)
    _response, headers = login("admin@example.com")
    created = client.post(
        "/users",
        headers=headers,
        json={
            "name": "Colaborador",
            "email": "New.User@Example.com",
            "password": "CollaboratorPassword123!",
            "role": "collaborator",
        },
    )
    assert created.status_code == 201
    user_id = created.json()["id"]
    assert created.json()["email"] == "new.user@example.com"
    assert "password_hash" not in created.json()

    edited = client.patch(
        f"/users/{user_id}", headers=headers, json={"name": "Nome Editado"}
    )
    assert edited.status_code == 200
    assert edited.json()["name"] == "Nome Editado"

    duplicate = client.post(
        "/users",
        headers=headers,
        json={
            "name": "Duplicado",
            "email": "NEW.USER@example.com",
            "password": "CollaboratorPassword123!",
        },
    )
    assert duplicate.status_code == 409


def test_last_active_admin_cannot_be_deactivated_or_demoted(client, user_factory, login) -> None:
    admin = user_factory(email="admin@example.com", role=UserRole.ADMIN)
    _response, headers = login("admin@example.com")
    for payload in ({"is_active": False}, {"role": "collaborator"}):
        response = client.patch(f"/users/{admin.id}", headers=headers, json=payload)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "last_active_admin"


def test_store_association_access_inactive_store_and_revocation(client, user_factory, login) -> None:
    user_factory(email="admin@example.com", role=UserRole.ADMIN)
    collaborator = user_factory(email="collab@example.com")
    _response, headers = login("admin@example.com")

    store_a = client.post("/stores", headers=headers, json={"name": "Loja A"}).json()
    store_b = client.post("/stores", headers=headers, json={"name": "Loja B"}).json()
    inactive = client.post(
        "/stores", headers=headers, json={"name": "Loja Inativa", "is_active": False}
    ).json()

    association = client.put(
        f"/users/{collaborator.id}/stores",
        headers=headers,
        json={"store_ids": [store_a["id"], inactive["id"]]},
    )
    assert association.status_code == 200

    client.cookies.clear()
    login("collab@example.com")
    visible = client.get("/stores")
    assert [store["id"] for store in visible.json()] == [store_a["id"]]
    assert client.get(f"/stores/{store_a['id']}").status_code == 200
    assert client.get(f"/stores/{store_b['id']}").status_code == 404
    assert client.get(f"/stores/{inactive['id']}").status_code == 404

    client.cookies.clear()
    _response, headers = login("admin@example.com")
    revoked = client.put(
        f"/users/{collaborator.id}/stores", headers=headers, json={"store_ids": []}
    )
    assert revoked.status_code == 200

    client.cookies.clear()
    login("collab@example.com")
    assert client.get(f"/stores/{store_a['id']}").status_code == 404


def test_admin_cannot_operationally_use_inactive_store(client, user_factory, login) -> None:
    user_factory(email="admin@example.com", role=UserRole.ADMIN)
    _response, headers = login("admin@example.com")
    store = client.post(
        "/stores", headers=headers, json={"name": "Inativa", "is_active": False}
    ).json()
    response = client.get(f"/stores/{store['id']}")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "inactive_store"
