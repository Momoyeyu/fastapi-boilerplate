from unittest.mock import MagicMock
from uuid import UUID

import pytest

from auth import service
from auth.dto import TokenPair
from auth.model import InvitationCode
from common import erri
from common.resp import Code
from user.model import User

_ALICE_ID = UUID("01936b2a-7c00-7000-8000-000000000001")
_INV_ID = UUID("01936b2a-7c00-7000-8000-0000000000a1")


def async_return(value):
    """Create an async function that returns the given value."""

    async def _inner(*args, **kwargs):
        return value

    return _inner


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Create a mock settings object with default test values."""
    mock = MagicMock()
    mock.require_invitation_code = False
    monkeypatch.setattr(service, "settings", mock)
    return mock


async def test_initiate_registration_email_exists(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "email_exists", async_return(True), raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        await service.initiate_registration("alice@test.com", "StrongPw1")
    assert exc.value.code == Code.CONFLICT


async def test_initiate_registration_success(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "email_exists", async_return(False), raising=True)
    code_created = {}

    def mock_create_code(email, purpose):
        code_created["email"] = email
        code_created["purpose"] = purpose
        return "123456"

    monkeypatch.setattr(service, "create_verification_code", mock_create_code, raising=True)
    monkeypatch.setattr(service, "send_verification_email", async_return(True), raising=True)

    await service.initiate_registration("alice@test.com", "StrongPw1")
    assert code_created["email"] == "alice@test.com"
    assert code_created["purpose"] == "register"


async def test_complete_registration_invalid_code(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "consume_verification_code", lambda *args: False, raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        await service.complete_registration("alice@test.com", "wrong", "StrongPw1")
    assert exc.value.code == Code.BAD_REQUEST


async def test_complete_registration_success(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "consume_verification_code", lambda *args: True, raising=True)
    monkeypatch.setattr(service, "email_exists", async_return(False), raising=True)
    monkeypatch.setattr(service, "consume_invitation_context", lambda email: None)

    user = User(id=_ALICE_ID, username="alice", email="alice@test.com", hashed_password="x")

    mock_token_pair = TokenPair(
        access_token="token-123",
        refresh_token="refresh-456",
        expires_in=3600,
        refresh_token_expires_in=604800,
    )
    monkeypatch.setattr(service, "create_token", lambda u: mock_token_pair, raising=True)

    monkeypatch.setattr(
        service,
        "create_user_with_tenant",
        async_return((user, MagicMock(), MagicMock())),
    )

    result = await service.complete_registration("alice@test.com", "123456", "StrongPw1")
    assert result.access_token == "token-123"


async def test_initiate_registration_requires_invitation_code(
    monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock
):
    mock_settings.require_invitation_code = True
    monkeypatch.setattr(service, "email_exists", async_return(False), raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        await service.initiate_registration("alice@test.com", "StrongPw1")
    assert exc.value.code == Code.BAD_REQUEST


async def test_initiate_registration_invalid_invitation_code(monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock):
    mock_settings.require_invitation_code = True
    monkeypatch.setattr(service, "email_exists", async_return(False), raising=True)
    monkeypatch.setattr(service, "validate_invitation_code", async_return(None))

    with pytest.raises(erri.BusinessError) as exc:
        await service.initiate_registration("alice@test.com", "StrongPw1", "BADCODE")
    assert exc.value.code == Code.BAD_REQUEST


async def test_initiate_registration_valid_invitation_code(monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock):
    mock_settings.require_invitation_code = True
    monkeypatch.setattr(service, "email_exists", async_return(False), raising=True)
    monkeypatch.setattr(service, "create_verification_code", lambda *a: "123456")
    monkeypatch.setattr(service, "send_verification_email", async_return(None))

    mock_inv = InvitationCode(id=_INV_ID, code="VALID", max_uses=10, used_count=0, is_active=True)
    monkeypatch.setattr(service, "validate_invitation_code", async_return(mock_inv))

    stored: dict[str, UUID] = {}
    monkeypatch.setattr(
        service,
        "store_invitation_context",
        lambda email, inv_id: stored.update({"inv_id": inv_id}),  # type: ignore[func-returns-value]
    )

    await service.initiate_registration("alice@test.com", "StrongPw1", "VALID")
    assert stored["inv_id"] == _INV_ID


async def test_initiate_registration_skips_invitation_when_disabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "email_exists", async_return(False), raising=True)
    monkeypatch.setattr(service, "create_verification_code", lambda *a: "123456")
    monkeypatch.setattr(service, "send_verification_email", async_return(None))

    # Should succeed without invitation code validation
    await service.initiate_registration("alice@test.com", "StrongPw1", "ANYCODE")


async def test_complete_registration_with_invitation_context(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "consume_verification_code", lambda *args: True, raising=True)
    monkeypatch.setattr(service, "email_exists", async_return(False), raising=True)
    monkeypatch.setattr(service, "consume_invitation_context", lambda email: _INV_ID)

    captured_kwargs: dict = {}

    async def mock_create_user_with_tenant(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return (
            User(id=_ALICE_ID, username="alice", email="alice@test.com", hashed_password="x"),
            MagicMock(),
            MagicMock(),
        )

    monkeypatch.setattr(service, "create_user_with_tenant", mock_create_user_with_tenant)

    mock_token_pair = TokenPair(
        access_token="token-123",
        refresh_token="refresh-456",
        expires_in=3600,
        refresh_token_expires_in=604800,
    )
    monkeypatch.setattr(service, "create_token", lambda u: mock_token_pair, raising=True)

    incremented: list[UUID] = []

    async def mock_increment(cid):
        incremented.append(cid)

    monkeypatch.setattr(service, "increment_used_count", mock_increment)

    await service.complete_registration("alice@test.com", "123456", "StrongPw1")
    assert captured_kwargs["invitation_code_id"] == _INV_ID
    assert incremented == [_INV_ID]
