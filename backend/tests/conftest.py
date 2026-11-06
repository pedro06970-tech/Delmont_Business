from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.store import Store, UserStore
from app.models.user import User, UserRole


@pytest.fixture(scope="session", autouse=True)
def migrated_test_database() -> Generator[None, None, None]:
    if "_test" not in settings.DATABASE_URL:
        raise RuntimeError("Os testes de persistência exigem um PostgreSQL isolado de teste.")
    alembic_config = Config("alembic.ini")
    command.upgrade(alembic_config, "head")
    yield


@pytest.fixture(autouse=True)
def clean_database(migrated_test_database) -> Generator[None, None, None]:
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE customer_consent_events, message_templates, customers, "
                "login_attempts, auth_sessions, user_stores, stores, users "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest.fixture
def db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def user_factory(db: Session):
    def create_user(
        *,
        name: str = "Usuário Teste",
        email: str = "user@example.com",
        password: str = "StrongPassword123!",
        role: UserRole = UserRole.COLLABORATOR,
        is_active: bool = True,
    ) -> User:
        user = User(
            name=name,
            email=email.casefold(),
            password_hash=hash_password(password),
            role=role,
            is_active=is_active,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return create_user


@pytest.fixture
def store_factory(db: Session):
    def create_store(
        *, name: str = "Loja Teste", is_active: bool = True, users: list[User] | None = None
    ) -> Store:
        store = Store(name=name, is_active=is_active)
        db.add(store)
        db.flush()
        for user in users or []:
            db.add(UserStore(user_id=user.id, store_id=store.id))
        db.commit()
        db.refresh(store)
        return store

    return create_store


@pytest.fixture
def login(client: TestClient):
    def perform(email: str, password: str = "StrongPassword123!"):
        response = client.post("/auth/login", json={"email": email, "password": password})
        csrf = client.cookies.get("delmont_csrf")
        headers = {"X-CSRF-Token": csrf} if csrf else {}
        return response, headers

    return perform
