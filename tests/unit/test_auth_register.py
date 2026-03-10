from unittest.mock import MagicMock

import pytest

from auth import password, register
from auth.token import TokenPair
from common import erri
from common.resp import Code
from user.model import User


def async_return(value):
    """Create an async function that returns the given value."""

    async def _inner(*args, **kwargs):
        return value

    return _inner


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Create a mock settings object with default test values."""
    mock = MagicMock()
    mock.password_salt = "salt"
    mock.require_invitation_code = False
    monkeypatch.setattr(password, "settings", mock)
    monkeypatch.setattr(register, "settings", mock)
    return mock


async def test_initiate_registration_email_exists(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(register, "email_exists", async_return(True), raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        await register.initiate_registration("alice@test.com", "pw")
    assert exc.value.code == Code.CONFLICT


async def test_initiate_registration_success(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(register, "email_exists", async_return(False), raising=True)
    code_created = {}

    def mock_create_code(email, purpose):
        code_created["email"] = email
        code_created["purpose"] = purpose
        return "123456"

    monkeypatch.setattr(register, "create_verification_code", mock_create_code, raising=True)
    monkeypatch.setattr(register, "send_verification_email", async_return(True), raising=True)

    await register.initiate_registration("alice@test.com", "pw")
    assert code_created["email"] == "alice@test.com"
    assert code_created["purpose"] == "register"


async def test_complete_registration_invalid_code(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(register, "consume_verification_code", lambda *args: False, raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        await register.complete_registration("alice@test.com", "wrong", "pw")
    assert exc.value.code == Code.BAD_REQUEST


async def test_complete_registration_success(monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock):
    monkeypatch.setattr(register, "consume_verification_code", lambda *args: True, raising=True)
    monkeypatch.setattr(register, "email_exists", async_return(False), raising=True)

    import auth.verification as verification_mod

    monkeypatch.setattr(verification_mod, "consume_invitation_context", lambda email: None)

    user = User(id=1, username="alice", email="alice@test.com", password="x")
    monkeypatch.setattr(register, "create_user", async_return(user), raising=True)

    mock_token_pair = TokenPair(
        access_token="token-123",
        refresh_token="refresh-456",
        expires_in=3600,
        refresh_token_expires_in=604800,
    )
    monkeypatch.setattr(register, "create_token", async_return(mock_token_pair), raising=True)

    result = await register.complete_registration("alice@test.com", "123456", "pw")
    assert result.access_token == "token-123"


async def test_initiate_registration_requires_invitation_code(
    monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock
):
    mock_settings.require_invitation_code = True
    monkeypatch.setattr(register, "email_exists", async_return(False), raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        await register.initiate_registration("alice@test.com", "pw")
    assert exc.value.code == Code.BAD_REQUEST


async def test_initiate_registration_invalid_invitation_code(monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock):
    mock_settings.require_invitation_code = True
    monkeypatch.setattr(register, "email_exists", async_return(False), raising=True)

    import invitation.model as inv_model

    monkeypatch.setattr(inv_model, "validate_invitation_code", async_return(None))

    with pytest.raises(erri.BusinessError) as exc:
        await register.initiate_registration("alice@test.com", "pw", "BADCODE")
    assert exc.value.code == Code.BAD_REQUEST


async def test_initiate_registration_valid_invitation_code(monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock):
    mock_settings.require_invitation_code = True
    monkeypatch.setattr(register, "email_exists", async_return(False), raising=True)
    monkeypatch.setattr(register, "create_verification_code", lambda *a: "123456")
    monkeypatch.setattr(register, "send_verification_email", async_return(None))

    import invitation.model as inv_model
    from invitation.model import InvitationCode

    mock_inv = InvitationCode(id=1, code="VALID", max_uses=10, used_count=0, is_active=True)
    monkeypatch.setattr(inv_model, "validate_invitation_code", async_return(mock_inv))

    import auth.verification as verification_mod

    stored: dict[str, int] = {}
    monkeypatch.setattr(
        verification_mod,
        "store_invitation_context",
        lambda email, inv_id: stored.update({"inv_id": inv_id}),  # type: ignore[func-returns-value]
    )

    await register.initiate_registration("alice@test.com", "pw", "VALID")
    assert stored["inv_id"] == 1


async def test_initiate_registration_skips_invitation_when_disabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(register, "email_exists", async_return(False), raising=True)
    monkeypatch.setattr(register, "create_verification_code", lambda *a: "123456")
    monkeypatch.setattr(register, "send_verification_email", async_return(None))

    # Should succeed without invitation code validation
    await register.initiate_registration("alice@test.com", "pw", "ANYCODE")


async def test_complete_registration_with_invitation_context(monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock):
    monkeypatch.setattr(register, "consume_verification_code", lambda *args: True, raising=True)
    monkeypatch.setattr(register, "email_exists", async_return(False), raising=True)

    import auth.verification as verification_mod

    monkeypatch.setattr(verification_mod, "consume_invitation_context", lambda email: 42)

    captured_kwargs: dict = {}

    async def mock_create_user(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return User(id=1, username="alice", email="alice@test.com", password="x")

    monkeypatch.setattr(register, "create_user", mock_create_user, raising=True)

    mock_token_pair = TokenPair(
        access_token="token-123",
        refresh_token="refresh-456",
        expires_in=3600,
        refresh_token_expires_in=604800,
    )
    monkeypatch.setattr(register, "create_token", async_return(mock_token_pair), raising=True)

    import invitation.model as inv_model

    incremented: list[int] = []

    async def mock_increment(cid):
        incremented.append(cid)

    monkeypatch.setattr(inv_model, "increment_used_count", mock_increment)

    await register.complete_registration("alice@test.com", "123456", "pw")
    assert captured_kwargs["invitation_code_id"] == 42
    assert incremented == [42]
