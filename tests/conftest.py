import os
import uuid

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/budget_tracker_test")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DEBUG", "true")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def register_user(client: TestClient, email: str | None = None) -> dict:
    email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Test User",
            "email": email,
            "password": "SecurePass123",
            "base_currency": "PHP",
            "timezone": "Asia/Manila",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return {
        "email": email,
        "password": "SecurePass123",
        "access_token": body["access_token"],
        "refresh_token": body["refresh_token"],
        "user_id": body["user"]["id"],
        "headers": {"Authorization": f"Bearer {body['access_token']}"},
    }


def create_account(client: TestClient, headers: dict, name: str = "Wallet", balance: str = "1000.00") -> dict:
    response = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={
            "name": name,
            "account_type": "CASH",
            "currency": "PHP",
            "opening_balance": balance,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def get_expense_category(client: TestClient, headers: dict) -> dict:
    response = client.get("/api/v1/categories?category_type=EXPENSE", headers=headers)
    assert response.status_code == 200
    return response.json()[0]


def get_income_category(client: TestClient, headers: dict) -> dict:
    response = client.get("/api/v1/categories?category_type=INCOME", headers=headers)
    assert response.status_code == 200
    return response.json()[0]


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    admin_url = settings.database_url.rsplit("/", 1)[0] + "/postgres"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    db_name = settings.database_url.rsplit("/", 1)[-1]
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": db_name},
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db() -> Session:
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db: Session):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def user(client: TestClient) -> dict:
    return register_user(client)


@pytest.fixture
def auth_headers(user: dict) -> dict[str, str]:
    return user["headers"]


@pytest.fixture
def second_user(client: TestClient) -> dict:
    return register_user(client, email=f"other-{uuid.uuid4().hex[:8]}@example.com")
