from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.security import verify_password
from app.models.auth import AuthSession


def test_valid_and_invalid_login_use_safe_password_hash(client, db, user_factory, login) -> None:
    user = user_factory(email="MixedCase@example.com")
    assert user.password_hash != "StrongPassword123!"
    assert user.password_hash.startswith("$argon2id$")
    assert verify_password("StrongPassword123!", user.password_hash)

    valid, _headers = login("MIXEDCASE@example.com")
    assert valid.status_code == 200
    assert valid.json()["email"] == "mixedcase@example.com"
    assert "password_hash" not in valid.json()

    client.cookies.clear()
    invalid, _headers = login("mixedcase@example.com", "wrong-password")
    assert invalid.status_code == 401
    assert invalid.json()["error"]["code"] == "invalid_credentials"


def test_inactive_user_cannot_authenticate(client, user_factory, login) -> None:
    user_factory(email="inactive@example.com", is_active=False)
    response, _headers = login("inactive@example.com")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_login_rate_limit_blocks_excessive_attempts(client, user_factory) -> None:
    user_factory(email="limited@example.com")
    for _ in range(5):
        response = client.post(
            "/auth/login",
            json={"email": "limited@example.com", "password": "wrong-password"},
        )
        assert response.status_code == 401
    blocked = client.post(
        "/auth/login",
        json={"email": "limited@example.com", "password": "StrongPassword123!"},
    )
    assert blocked.status_code == 429


def test_expired_session_and_logout_are_rejected(client, db, user_factory, login) -> None:
    user_factory(email="session@example.com")
    response, headers = login("session@example.com")
    assert response.status_code == 200

    session = db.scalar(select(AuthSession))
    assert session is not None
    session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert client.get("/auth/me").status_code == 401

    client.cookies.clear()
    response, headers = login("session@example.com")
    assert response.status_code == 200
    logout = client.post("/auth/logout", headers=headers)
    assert logout.status_code == 200
    assert client.get("/auth/me").status_code == 401


def test_change_password_revokes_sessions(client, user_factory, login) -> None:
    user_factory(email="password@example.com")
    _response, headers = login("password@example.com")
    changed = client.post(
        "/auth/change-password",
        headers=headers,
        json={
            "current_password": "StrongPassword123!",
            "new_password": "AnotherStrongPassword456!",
        },
    )
    assert changed.status_code == 200
    assert client.get("/auth/me").status_code == 401

    client.cookies.clear()
    old_login, _ = login("password@example.com")
    assert old_login.status_code == 401
    new_login, _ = login("password@example.com", "AnotherStrongPassword456!")
    assert new_login.status_code == 200


def test_csrf_is_required_for_authenticated_mutations(client, user_factory, login) -> None:
    user_factory(email="csrf@example.com")
    login("csrf@example.com")
    response = client.post(
        "/auth/change-password",
        json={
            "current_password": "StrongPassword123!",
            "new_password": "AnotherStrongPassword456!",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "invalid_csrf"


def test_unauthenticated_access_is_denied(client) -> None:
    for path in ("/auth/me", "/users", "/stores"):
        assert client.get(path).status_code == 401
