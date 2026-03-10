"""
Integration test fixtures.

Uses a temporary SQLite database to isolate tests from the real database.
"""

import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as create_sync_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from auth import model as auth_model
from conf import db as db_module
from conf import redis as redis_module
from conf.db import Base
from invitation import model as invitation_model
from user import model as user_model


@pytest.fixture(scope="function")
def test_engine():
    """Create a fresh temporary SQLite database for each test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Create tables using sync engine (DDL doesn't need async)
    sync_engine = create_sync_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()

    # Create async engine for runtime use
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    yield engine
    engine.sync_engine.dispose()
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture(scope="function")
def test_session_local(test_engine):
    """Create an async session factory bound to the test engine."""
    return async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="function")
def client(test_engine, test_session_local, monkeypatch) -> TestClient:
    """
    Create a TestClient with the test database engine.

    Patches the engine and session factory in both db and model modules.
    """
    monkeypatch.setattr(db_module, "engine", test_engine)
    monkeypatch.setattr(db_module, "AsyncSessionLocal", test_session_local)
    monkeypatch.setattr(user_model, "AsyncSessionLocal", test_session_local)
    monkeypatch.setattr(auth_model, "AsyncSessionLocal", test_session_local)
    monkeypatch.setattr(invitation_model, "AsyncSessionLocal", test_session_local)

    # Import create_app after patching to ensure patches are in effect
    from main import create_app

    app = create_app()

    with TestClient(app) as test_client:
        yield test_client


class FakeRedis:
    """In-memory Redis mock so tests run without a real Redis server."""

    def __init__(self):
        self._store: dict[str, str] = {}

    def setex(self, key, ttl, value):
        self._store[key] = value

    def get(self, key):
        return self._store.get(key)

    def delete(self, key):
        self._store.pop(key, None)

    def flushdb(self):
        self._store.clear()

    def close(self):
        pass


@pytest.fixture(autouse=True)
def redis_test_db(monkeypatch):
    """Provide a FakeRedis instance so integration tests don't need a real Redis."""
    fake = FakeRedis()
    monkeypatch.setattr(redis_module, "_client", fake)
    yield fake
    monkeypatch.setattr(redis_module, "_client", None)


@pytest.fixture(autouse=True)
def mock_email(monkeypatch):
    """Mock email sending to avoid consuming real Resend quota."""
    sent_emails: list[dict[str, str]] = []

    async def fake_send(email, code, purpose):
        sent_emails.append({"email": email, "code": code, "purpose": purpose})
        return True

    from auth import password as password_module
    from auth import register as register_module

    monkeypatch.setattr(register_module, "send_verification_email", fake_send)
    monkeypatch.setattr(password_module, "send_verification_email", fake_send)
    return sent_emails


@pytest.fixture
def register_and_verify(client):
    """Register a user through the two-step process and return the response body."""

    def _do(email: str, password: str, invitation_code: str | None = None) -> dict:
        from conf.redis import get_redis

        body: dict = {"email": email, "password": password}
        if invitation_code is not None:
            body["invitation_code"] = invitation_code
        client.post("/auth/register", json=body)
        key = f"verification:{email.lower()}:register"
        code = get_redis().get(key)
        response = client.post(
            "/auth/register/verify",
            json={"email": email, "code": code, "password": password},
        )
        return response.json()

    return _do


@pytest.fixture
def auth_header(register_and_verify):
    """Get an Authorization header for a freshly registered user."""

    def _do(email: str, password: str) -> dict:
        body = register_and_verify(email, password)
        return {"Authorization": f"Bearer {body['data']['access_token']}"}

    return _do


@pytest_asyncio.fixture(scope="function")
async def session(test_session_local) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for direct database operations in tests."""
    async with test_session_local() as session:
        yield session
