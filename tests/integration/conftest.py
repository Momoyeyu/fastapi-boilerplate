"""
Integration test fixtures.

Uses a temporary SQLite database to isolate tests from the real database.
Patches bcrypt with fast SHA-256 hashing for speed.
"""

import hashlib
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as create_sync_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from auth import model as auth_model
from auth import service as service_module
from common import utils as utils_module
from conf import db as db_module
from conf import redis as redis_module
from conf.db import Base
from tenant import model as tenant_model
from user import model as user_model

# ---------------------------------------------------------------------------
# Fast password hashing (replaces bcrypt ~200ms/call with SHA256 <1ms/call)
# ---------------------------------------------------------------------------

_FAST_PREFIX = "$fast$"


def _fast_hash(password: str) -> str:
    return _FAST_PREFIX + hashlib.sha256(password.encode()).hexdigest()


def _fast_verify(plain_password: str, hashed_password: str) -> bool:
    return _fast_hash(plain_password) == hashed_password


@pytest.fixture(autouse=True)
def fast_password_hash(monkeypatch):
    """Replace bcrypt with fast SHA-256 for integration test speed."""
    # Patch in the definition module
    monkeypatch.setattr(utils_module, "get_password_hash", _fast_hash)
    monkeypatch.setattr(utils_module, "verify_password", _fast_verify)

    # Patch in all modules that do `from common.utils import ...`
    from tenant import service as tenant_service_mod
    from user import service as user_service_mod

    monkeypatch.setattr(service_module, "get_password_hash", _fast_hash)
    monkeypatch.setattr(service_module, "verify_password", _fast_verify)
    monkeypatch.setattr(user_service_mod, "get_password_hash", _fast_hash)
    monkeypatch.setattr(user_service_mod, "verify_password", _fast_verify)
    monkeypatch.setattr(tenant_service_mod, "get_password_hash", _fast_hash)


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


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
    monkeypatch.setattr(tenant_model, "AsyncSessionLocal", test_session_local)

    from tenant import service as tenant_service_mod

    monkeypatch.setattr(tenant_service_mod, "AsyncSessionLocal", test_session_local)

    # Import create_app after patching to ensure patches are in effect
    from main import create_app

    app = create_app()

    with TestClient(app) as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# FakeRedis mock
# ---------------------------------------------------------------------------


class FakePipeline:
    """Minimal pipeline mock that buffers and executes commands."""

    def __init__(self, redis):
        self._redis = redis
        self._commands: list[tuple] = []

    def set(self, key, value, ex=None):
        self._commands.append(("set", key, value, ex))
        return self

    def srem(self, key, *members):
        self._commands.append(("srem", key, *members))
        return self

    def sadd(self, key, *members):
        self._commands.append(("sadd", key, *members))
        return self

    def execute(self):
        for cmd in self._commands:
            getattr(self._redis, cmd[0])(*cmd[1:])
        self._commands.clear()


class FakeRedis:
    """In-memory Redis mock supporting string and set operations."""

    def __init__(self):
        self._store: dict[str, str] = {}
        self._sets: dict[str, set[str]] = {}

    # String operations
    def setex(self, key, ttl, value):
        self._store[key] = value

    def set(self, key, value, ex=None):
        self._store[key] = value

    def get(self, key):
        return self._store.get(key)

    def getdel(self, key):
        return self._store.pop(key, None)

    def delete(self, key):
        self._store.pop(key, None)
        self._sets.pop(key, None)

    # Set operations
    def sadd(self, key, *members):
        if key not in self._sets:
            self._sets[key] = set()
        for m in members:
            self._sets[key].add(m)

    def smembers(self, key):
        return self._sets.get(key, set()).copy()

    def srem(self, key, *members):
        if key in self._sets:
            for m in members:
                self._sets[key].discard(m)

    def flushdb(self):
        self._store.clear()
        self._sets.clear()

    def expire(self, key, ttl):
        pass  # TTL not enforced in tests

    def pipeline(self):
        return FakePipeline(self)

    def close(self):
        pass


@pytest.fixture(autouse=True)
def redis_test_db(monkeypatch):
    """Provide a FakeRedis instance so integration tests don't need a real Redis."""
    fake = FakeRedis()
    monkeypatch.setattr(redis_module, "_client", fake)
    yield fake
    monkeypatch.setattr(redis_module, "_client", None)


# ---------------------------------------------------------------------------
# Email mock
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_email(monkeypatch):
    """Mock email sending to avoid consuming real Resend quota."""
    sent_emails: list[dict[str, str]] = []

    async def fake_send(email, code, purpose):
        sent_emails.append({"email": email, "code": code, "purpose": purpose})
        return True

    monkeypatch.setattr(service_module, "send_verification_email", fake_send)

    from tenant import service as tenant_service_mod

    async def fake_send_invite(email, tenant_name, invite_url):
        sent_emails.append({"email": email, "tenant_name": tenant_name, "type": "invite"})
        return True

    async def fake_send_added(email, tenant_name):
        sent_emails.append({"email": email, "tenant_name": tenant_name, "type": "added"})
        return True

    monkeypatch.setattr(tenant_service_mod, "_send_invite_email", fake_send_invite)
    monkeypatch.setattr(tenant_service_mod, "_send_added_email", fake_send_added)
    return sent_emails


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def register_and_verify(client):
    """Register a user through the two-step process and return the response body."""

    def _do(email: str, password: str, invitation_code: str | None = None) -> dict:
        from conf.redis import get_redis

        body: dict = {"email": email, "password": password}
        if invitation_code is not None:
            body["invitation_code"] = invitation_code
        client.post("/api/v1/auth/register", json=body)
        key = f"verification:{email.lower()}:register"
        code = get_redis().get(key)
        response = client.post(
            "/api/v1/auth/register/verify",
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
