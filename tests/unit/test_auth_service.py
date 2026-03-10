import hashlib
from unittest.mock import MagicMock

import pytest

from auth import password, register, token
from auth.token import TokenPair
from common import erri
from common.resp import Code
from user.model import User


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Create a mock settings object with default test values."""
    mock = MagicMock()
    mock.password_salt = "salt"
    mock.require_invitation_code = False
    monkeypatch.setattr(token, "settings", mock)
    monkeypatch.setattr(password, "settings", mock)
    monkeypatch.setattr(register, "settings", mock)
    return mock


def test_get_password_hash_uses_salt(mock_settings: MagicMock):
    pw = "pw"
    expected = hashlib.sha512((pw + "salt").encode("utf-8")).hexdigest()
    assert password.get_password_hash(pw) == expected


def test_login_user_user_not_found(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(token, "get_user_by_identifier", lambda identifier: None, raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        token.login_user("alice", "pw")
    assert exc.value.code == Code.UNAUTHORIZED


def test_login_user_password_mismatch(monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock):
    user = User(id=1, username="alice", email="alice@test.com", password=password.get_password_hash("correct"))
    monkeypatch.setattr(token, "get_user_by_identifier", lambda identifier: user, raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        token.login_user("alice", "wrong")
    assert exc.value.code == Code.UNAUTHORIZED


def test_login_user_user_without_id(monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock):
    user = User(id=None, username="alice", email="alice@test.com", password=password.get_password_hash("pw"))
    monkeypatch.setattr(token, "get_user_by_identifier", lambda identifier: user, raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        token.login_user("alice", "pw")
    assert exc.value.code == Code.UNAUTHORIZED


def test_login_user_success_creates_token(monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock):
    user = User(id=7, username="alice", email="alice@test.com", password=password.get_password_hash("pw"))
    monkeypatch.setattr(token, "get_user_by_identifier", lambda identifier: user, raising=True)

    captured: dict[str, object] = {}
    mock_token_pair = TokenPair(
        access_token="token-123",
        refresh_token="refresh-456",
        expires_in=3600,
        refresh_token_expires_in=604800,
    )

    def _create_token(passed_user: object):
        captured["user"] = passed_user
        return mock_token_pair

    monkeypatch.setattr(token, "create_token", _create_token, raising=True)

    token_pair = token.login_user("alice", "pw")
    assert token_pair.access_token == "token-123"
    assert token_pair.refresh_token == "refresh-456"
    assert captured["user"] is user


def test_login_user_with_email(monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock):
    user = User(id=7, username="alice", email="alice@test.com", password=password.get_password_hash("pw"))
    monkeypatch.setattr(token, "get_user_by_identifier", lambda identifier: user, raising=True)

    mock_token_pair = TokenPair(
        access_token="token-123",
        refresh_token="refresh-456",
        expires_in=3600,
        refresh_token_expires_in=604800,
    )
    monkeypatch.setattr(token, "create_token", lambda _: mock_token_pair, raising=True)

    token_pair = token.login_user("alice@test.com", "pw")
    assert token_pair.access_token == "token-123"


def test_initiate_registration_email_exists(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(register, "email_exists", lambda email: True, raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        register.initiate_registration("alice@test.com", "pw")
    assert exc.value.code == Code.CONFLICT


def test_initiate_registration_success(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(register, "email_exists", lambda email: False, raising=True)
    code_created = {}

    def mock_create_code(email, purpose):
        code_created["email"] = email
        code_created["purpose"] = purpose
        return "123456"

    monkeypatch.setattr(register, "create_verification_code", mock_create_code, raising=True)
    monkeypatch.setattr(register, "send_verification_email", lambda *args: True, raising=True)

    register.initiate_registration("alice@test.com", "pw")
    assert code_created["email"] == "alice@test.com"
    assert code_created["purpose"] == "register"


def test_request_password_reset_sends_code(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(password, "email_exists", lambda email: True, raising=True)
    sent = {}

    monkeypatch.setattr(password, "create_verification_code", lambda email, purpose: "654321", raising=True)

    def mock_send(email, code, purpose):
        sent["email"] = email
        sent["code"] = code
        sent["purpose"] = purpose
        return True

    monkeypatch.setattr(password, "send_verification_email", mock_send, raising=True)

    password.request_password_reset("alice@test.com")
    assert sent["email"] == "alice@test.com"
    assert sent["code"] == "654321"
    assert sent["purpose"] == "reset_password"


def test_complete_registration_invalid_code(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(register, "consume_verification_code", lambda *args: False, raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        register.complete_registration("alice@test.com", "wrong", "pw")
    assert exc.value.code == Code.BAD_REQUEST


def test_complete_registration_success(monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock):
    monkeypatch.setattr(register, "consume_verification_code", lambda *args: True, raising=True)
    monkeypatch.setattr(register, "email_exists", lambda email: False, raising=True)

    import auth.verification as verification_mod

    monkeypatch.setattr(verification_mod, "consume_invitation_context", lambda email: None)

    user = User(id=1, username="alice", email="alice@test.com", password="x")
    monkeypatch.setattr(register, "create_user", lambda *args, **kwargs: user, raising=True)

    mock_token_pair = TokenPair(
        access_token="token-123",
        refresh_token="refresh-456",
        expires_in=3600,
        refresh_token_expires_in=604800,
    )
    monkeypatch.setattr(register, "create_token", lambda _: mock_token_pair, raising=True)

    result = register.complete_registration("alice@test.com", "123456", "pw")
    assert result.access_token == "token-123"


def test_initiate_registration_requires_invitation_code(monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock):
    mock_settings.require_invitation_code = True
    monkeypatch.setattr(register, "email_exists", lambda email: False, raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        register.initiate_registration("alice@test.com", "pw")
    assert exc.value.code == Code.BAD_REQUEST


def test_initiate_registration_invalid_invitation_code(monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock):
    mock_settings.require_invitation_code = True
    monkeypatch.setattr(register, "email_exists", lambda email: False, raising=True)

    import invitation.model as inv_model

    monkeypatch.setattr(inv_model, "validate_invitation_code", lambda code: None)

    with pytest.raises(erri.BusinessError) as exc:
        register.initiate_registration("alice@test.com", "pw", "BADCODE")
    assert exc.value.code == Code.BAD_REQUEST


def test_initiate_registration_valid_invitation_code(monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock):
    mock_settings.require_invitation_code = True
    monkeypatch.setattr(register, "email_exists", lambda email: False, raising=True)
    monkeypatch.setattr(register, "create_verification_code", lambda *a: "123456")
    monkeypatch.setattr(register, "send_verification_email", lambda *a: None)

    import invitation.model as inv_model
    from invitation.model import InvitationCode

    mock_inv = InvitationCode(id=1, code="VALID", max_uses=10, used_count=0, is_active=True)
    monkeypatch.setattr(inv_model, "validate_invitation_code", lambda code: mock_inv)

    import auth.verification as verification_mod

    stored: dict[str, int] = {}
    monkeypatch.setattr(
        verification_mod,
        "store_invitation_context",
        lambda email, inv_id: stored.update({"inv_id": inv_id}),  # type: ignore[func-returns-value]
    )

    register.initiate_registration("alice@test.com", "pw", "VALID")
    assert stored["inv_id"] == 1


def test_initiate_registration_skips_invitation_when_disabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(register, "email_exists", lambda email: False, raising=True)
    monkeypatch.setattr(register, "create_verification_code", lambda *a: "123456")
    monkeypatch.setattr(register, "send_verification_email", lambda *a: None)

    # Should succeed without invitation code validation
    register.initiate_registration("alice@test.com", "pw", "ANYCODE")


def test_complete_registration_with_invitation_context(monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock):
    monkeypatch.setattr(register, "consume_verification_code", lambda *args: True, raising=True)
    monkeypatch.setattr(register, "email_exists", lambda email: False, raising=True)

    import auth.verification as verification_mod

    monkeypatch.setattr(verification_mod, "consume_invitation_context", lambda email: 42)

    captured_kwargs: dict = {}

    def mock_create_user(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return User(id=1, username="alice", email="alice@test.com", password="x")

    monkeypatch.setattr(register, "create_user", mock_create_user, raising=True)

    mock_token_pair = TokenPair(
        access_token="token-123",
        refresh_token="refresh-456",
        expires_in=3600,
        refresh_token_expires_in=604800,
    )
    monkeypatch.setattr(register, "create_token", lambda _: mock_token_pair, raising=True)

    import invitation.model as inv_model

    incremented: list[int] = []
    monkeypatch.setattr(inv_model, "increment_used_count", lambda cid: incremented.append(cid))

    register.complete_registration("alice@test.com", "123456", "pw")
    assert captured_kwargs["invitation_code_id"] == 42
    assert incremented == [42]
