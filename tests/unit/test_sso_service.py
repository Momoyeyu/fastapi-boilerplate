"""Unit tests for SSO service logic."""

from unittest.mock import patch
from uuid import UUID

import pytest

from auth import sso_service
from auth.dto import TokenPair
from auth.oauth_model import OAuthAccount
from common import erri
from common.resp import Code
from user.model import User

_ALICE_ID = UUID("01936b2a-7c00-7000-8000-000000000001")
_BOB_ID = UUID("01936b2a-7c00-7000-8000-000000000002")


def async_return(value):
    async def _inner(*args, **kwargs):
        return value

    return _inner


class FakeRedis:
    def __init__(self):
        self._store = {}

    def setex(self, key, ttl, value):
        self._store[key] = value

    def get(self, key):
        return self._store.get(key)

    def delete(self, key):
        self._store.pop(key, None)


@pytest.fixture
def fake_redis():
    fake = FakeRedis()
    with patch("auth.sso_service.get_redis", return_value=fake):
        yield fake


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------


def test_store_and_consume_state(fake_redis):
    state = sso_service._store_state("google")
    assert state is not None
    data = sso_service._consume_state(state)
    assert data is not None
    assert data["provider"] == "google"
    assert data["user_id"] is None


def test_store_state_with_user_id(fake_redis):
    state = sso_service._store_state("github", user_id=_ALICE_ID)
    data = sso_service._consume_state(state)
    assert data["user_id"] == str(_ALICE_ID)


def test_consume_state_only_once(fake_redis):
    state = sso_service._store_state("google")
    sso_service._consume_state(state)
    assert sso_service._consume_state(state) is None


def test_consume_invalid_state(fake_redis):
    assert sso_service._consume_state("nonexistent") is None


# ---------------------------------------------------------------------------
# Callback URL
# ---------------------------------------------------------------------------


def test_callback_url_defaults_to_frontend(monkeypatch):
    monkeypatch.setattr(
        sso_service,
        "settings",
        type("S", (), {"oauth_callback_base_url": "", "frontend_url": "http://localhost:3000"})(),
    )
    url = sso_service._callback_url("google")
    assert url == "http://localhost:3000/auth/callback/google"


def test_callback_url_override(monkeypatch):
    monkeypatch.setattr(
        sso_service,
        "settings",
        type(
            "S", (), {"oauth_callback_base_url": "https://custom.example.com", "frontend_url": "http://localhost:3000"}
        )(),
    )
    url = sso_service._callback_url("github")
    assert url == "https://custom.example.com/auth/callback/github"


def test_callback_url_same_for_login_and_link(monkeypatch):
    """Login and link use the same callback URL — state distinguishes them."""
    monkeypatch.setattr(
        sso_service,
        "settings",
        type("S", (), {"oauth_callback_base_url": "", "frontend_url": "https://app.example.com"})(),
    )
    url = sso_service._callback_url("google")
    assert url == "https://app.example.com/auth/callback/google"


# ---------------------------------------------------------------------------
# SSO callback logic
# ---------------------------------------------------------------------------


async def test_callback_invalid_state(fake_redis):
    with pytest.raises(erri.BusinessError) as exc:
        await sso_service.handle_sso_callback("google", "code123", "bad_state")
    assert exc.value.code == Code.BAD_REQUEST


async def test_callback_state_provider_mismatch(fake_redis):
    state = sso_service._store_state("google")
    with pytest.raises(erri.BusinessError) as exc:
        await sso_service.handle_sso_callback("github", "code123", state)
    assert exc.value.code == Code.BAD_REQUEST


async def test_callback_existing_oauth_account(monkeypatch, fake_redis):
    """If oauth_account exists, return tokens for linked user."""
    state = sso_service._store_state("google")
    user = User(id=_ALICE_ID, username="alice", email="alice@test.com", hashed_password=None)
    oauth_acc = OAuthAccount(user_id=_ALICE_ID, provider="google", provider_user_id="g123")
    token_pair = TokenPair(access_token="at", refresh_token="rt", expires_in=3600, refresh_token_expires_in=604800)

    monkeypatch.setattr(
        sso_service,
        "_get_client",
        lambda p: type(
            "C",
            (),
            {
                "get_access_token": async_return({"access_token": "tok123"}),
            },
        )(),
    )
    monkeypatch.setattr(
        sso_service,
        "_fetch_user_info",
        async_return(
            {
                "id": "g123",
                "email": "alice@gmail.com",
                "email_verified": True,
                "name": "Alice",
            }
        ),
    )
    monkeypatch.setattr(sso_service, "get_oauth_account", async_return(oauth_acc))
    monkeypatch.setattr(sso_service, "get_user_by_id", async_return(user))
    monkeypatch.setattr(sso_service, "create_token", lambda u: token_pair)

    result = await sso_service.handle_sso_callback("google", "code", state)
    assert result.access_token == "at"


async def test_callback_auto_link_by_email(monkeypatch, fake_redis):
    """If no oauth_account but email matches existing user, auto-link."""
    state = sso_service._store_state("github")
    user = User(
        id=_ALICE_ID,
        username="alice",
        email="alice@test.com",
        hashed_password="hash",
        is_active=True,
        is_deleted=False,
    )
    token_pair = TokenPair(access_token="at", refresh_token="rt", expires_in=3600, refresh_token_expires_in=604800)

    created_accounts = []

    monkeypatch.setattr(
        sso_service,
        "_get_client",
        lambda p: type(
            "C",
            (),
            {
                "get_access_token": async_return({"access_token": "tok"}),
            },
        )(),
    )
    monkeypatch.setattr(
        sso_service,
        "_fetch_user_info",
        async_return(
            {
                "id": "gh456",
                "email": "alice@test.com",
                "email_verified": True,
                "name": "Alice",
            }
        ),
    )
    monkeypatch.setattr(sso_service, "get_oauth_account", async_return(None))
    monkeypatch.setattr(sso_service, "get_user_by_email", async_return(user))
    monkeypatch.setattr(sso_service, "create_token", lambda u: token_pair)

    async def mock_create(*args, **kwargs):
        created_accounts.append(args)
        return OAuthAccount(user_id=_ALICE_ID, provider="github", provider_user_id="gh456")

    monkeypatch.setattr(sso_service, "create_oauth_account", mock_create)

    result = await sso_service.handle_sso_callback("github", "code", state)
    assert result.access_token == "at"
    assert len(created_accounts) == 1


async def test_callback_creates_new_user(monkeypatch, fake_redis):
    """If no match at all, create new user + oauth_account atomically."""
    state = sso_service._store_state("google")
    user = User(id=_ALICE_ID, username="user_abc", email="new@gmail.com", hashed_password=None)
    token_pair = TokenPair(
        access_token="new_at", refresh_token="new_rt", expires_in=3600, refresh_token_expires_in=604800
    )

    monkeypatch.setattr(
        sso_service,
        "_get_client",
        lambda p: type(
            "C",
            (),
            {
                "get_access_token": async_return({"access_token": "tok"}),
            },
        )(),
    )
    monkeypatch.setattr(
        sso_service,
        "_fetch_user_info",
        async_return(
            {
                "id": "g789",
                "email": "new@gmail.com",
                "email_verified": True,
                "name": "New User",
            }
        ),
    )
    monkeypatch.setattr(sso_service, "get_oauth_account", async_return(None))
    monkeypatch.setattr(sso_service, "get_user_by_email", async_return(None))
    monkeypatch.setattr(sso_service, "_create_sso_user_with_tenant", async_return(user))
    monkeypatch.setattr(sso_service, "create_token", lambda u: token_pair)

    result = await sso_service.handle_sso_callback("google", "code", state)
    assert result.access_token == "new_at"


# ---------------------------------------------------------------------------
# Unlink
# ---------------------------------------------------------------------------


async def test_unlink_not_linked(monkeypatch):
    user = User(id=_ALICE_ID, username="alice", email="a@t.com", hashed_password="hash")
    monkeypatch.setattr(sso_service, "get_user_by_id", async_return(user))
    monkeypatch.setattr(sso_service, "get_oauth_accounts_for_user", async_return([]))

    with pytest.raises(erri.BusinessError) as exc:
        await sso_service.unlink_provider(_ALICE_ID, "google")
    assert exc.value.code == Code.NOT_FOUND


async def test_unlink_last_method_rejected(monkeypatch):
    """Cannot unlink when it's the only login method and no password."""
    user = User(id=_ALICE_ID, username="alice", email="a@t.com", hashed_password=None)
    oauth_acc = OAuthAccount(user_id=_ALICE_ID, provider="google", provider_user_id="g123")
    monkeypatch.setattr(sso_service, "get_user_by_id", async_return(user))
    monkeypatch.setattr(sso_service, "get_oauth_accounts_for_user", async_return([oauth_acc]))

    with pytest.raises(erri.BusinessError) as exc:
        await sso_service.unlink_provider(_ALICE_ID, "google")
    assert exc.value.code == Code.BAD_REQUEST


async def test_unlink_succeeds_with_password(monkeypatch):
    """Can unlink when user has a password."""
    user = User(id=_ALICE_ID, username="alice", email="a@t.com", hashed_password="hash")
    oauth_acc = OAuthAccount(user_id=_ALICE_ID, provider="google", provider_user_id="g123")
    monkeypatch.setattr(sso_service, "get_user_by_id", async_return(user))
    monkeypatch.setattr(sso_service, "get_oauth_accounts_for_user", async_return([oauth_acc]))
    monkeypatch.setattr(sso_service, "delete_oauth_account", async_return(True))

    await sso_service.unlink_provider(_ALICE_ID, "google")  # should not raise


async def test_unlink_succeeds_with_multiple_providers(monkeypatch):
    """Can unlink one provider when another is still linked."""
    user = User(id=_ALICE_ID, username="alice", email="a@t.com", hashed_password=None)
    google_acc = OAuthAccount(user_id=_ALICE_ID, provider="google", provider_user_id="g123")
    github_acc = OAuthAccount(user_id=_ALICE_ID, provider="github", provider_user_id="gh456")
    monkeypatch.setattr(sso_service, "get_user_by_id", async_return(user))
    monkeypatch.setattr(sso_service, "get_oauth_accounts_for_user", async_return([google_acc, github_acc]))
    monkeypatch.setattr(sso_service, "delete_oauth_account", async_return(True))

    await sso_service.unlink_provider(_ALICE_ID, "google")  # should not raise


# ---------------------------------------------------------------------------
# Get linked providers
# ---------------------------------------------------------------------------


async def test_get_linked_providers(monkeypatch):
    from datetime import UTC, datetime

    user = User(id=_ALICE_ID, username="alice", email="a@t.com", hashed_password="hash")
    now = datetime.now(UTC)
    acc = OAuthAccount(
        user_id=_ALICE_ID,
        provider="google",
        provider_user_id="g123",
        provider_email="alice@gmail.com",
        created_at=now,
    )
    monkeypatch.setattr(sso_service, "get_user_by_id", async_return(user))
    monkeypatch.setattr(sso_service, "get_oauth_accounts_for_user", async_return([acc]))

    result = await sso_service.get_linked_providers(_ALICE_ID)
    assert result["has_password"] is True
    assert len(result["providers"]) == 1
    assert result["providers"][0]["provider"] == "google"


async def test_get_linked_providers_no_password(monkeypatch):
    user = User(id=_ALICE_ID, username="alice", email="a@t.com", hashed_password=None)
    monkeypatch.setattr(sso_service, "get_user_by_id", async_return(user))
    monkeypatch.setattr(sso_service, "get_oauth_accounts_for_user", async_return([]))

    result = await sso_service.get_linked_providers(_ALICE_ID)
    assert result["has_password"] is False
    assert len(result["providers"]) == 0
