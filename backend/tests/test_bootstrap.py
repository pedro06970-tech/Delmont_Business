from app.models.user import UserRole
from app.services.bootstrap import bootstrap_admin


def test_admin_bootstrap_is_idempotent_and_does_not_replace_password(db) -> None:
    first, created = bootstrap_admin(
        db,
        name="Administrador",
        email="ADMIN@example.com",
        password="InitialAdminPassword123!",
    )
    original_hash = first.password_hash
    assert created is True
    assert first.role == UserRole.ADMIN

    second, created_again = bootstrap_admin(
        db,
        name="Outro Nome",
        email="admin@example.com",
        password="DifferentPassword456!",
    )
    assert created_again is False
    assert second.id == first.id
    assert second.password_hash == original_hash
