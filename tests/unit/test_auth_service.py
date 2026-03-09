import hashlib
from unittest.mock import MagicMock

import pytest

from auth import service
from auth.service import TokenPair
from common import erri
from user.model import User


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Create a mock settings object with default test values."""
    mock = MagicMock()
    mock.password_salt = "salt"
    monkeypatch.setattr(service, "settings", mock)
    return mock


def test_get_password_hash_uses_salt(mock_settings: MagicMock):
    password = "pw"
    expected = hashlib.sha512((password + "salt").encode("utf-8")).hexdigest()
    assert service.get_password_hash(password) == expected


def test_login_user_user_not_found(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "get_user_by_identifier", lambda identifier: None, raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        service.login_user("alice", "pw")
    assert exc.value.status_code == 401


def test_login_user_password_mismatch(monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock):
    user = User(id=1, username="alice", email="alice@test.com", password=service.get_password_hash("correct"))
    monkeypatch.setattr(service, "get_user_by_identifier", lambda identifier: user, raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        service.login_user("alice", "wrong")
    assert exc.value.status_code == 401


def test_login_user_user_without_id(monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock):
    user = User(id=None, username="alice", email="alice@test.com", password=service.get_password_hash("pw"))
    monkeypatch.setattr(service, "get_user_by_identifier", lambda identifier: user, raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        service.login_user("alice", "pw")
    assert exc.value.status_code == 401


def test_login_user_success_creates_token(monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock):
    user = User(id=7, username="alice", email="alice@test.com", password=service.get_password_hash("pw"))
    monkeypatch.setattr(service, "get_user_by_identifier", lambda identifier: user, raising=True)

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

    monkeypatch.setattr(service, "create_token", _create_token, raising=True)

    token_pair = service.login_user("alice", "pw")
    assert token_pair.access_token == "token-123"
    assert token_pair.refresh_token == "refresh-456"
    assert captured["user"] is user


def test_login_user_with_email(monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock):
    user = User(id=7, username="alice", email="alice@test.com", password=service.get_password_hash("pw"))
    monkeypatch.setattr(service, "get_user_by_identifier", lambda identifier: user, raising=True)

    mock_token_pair = TokenPair(
        access_token="token-123",
        refresh_token="refresh-456",
        expires_in=3600,
        refresh_token_expires_in=604800,
    )
    monkeypatch.setattr(service, "create_token", lambda _: mock_token_pair, raising=True)

    token_pair = service.login_user("alice@test.com", "pw")
    assert token_pair.access_token == "token-123"


def test_initiate_registration_email_exists(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "email_exists", lambda email: True, raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        service.initiate_registration("alice@test.com", "pw")
    assert exc.value.status_code == 409


def test_initiate_registration_success(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "email_exists", lambda email: False, raising=True)
    code_created = {}

    def mock_create_code(email, purpose):
        code_created["email"] = email
        code_created["purpose"] = purpose
        return "123456"

    monkeypatch.setattr(service, "create_verification_code", mock_create_code, raising=True)
    monkeypatch.setattr(service, "send_verification_email", lambda *args: True, raising=True)

    service.initiate_registration("alice@test.com", "pw")
    assert code_created["email"] == "alice@test.com"
    assert code_created["purpose"] == "register"


def test_request_password_reset_sends_code(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "email_exists", lambda email: True, raising=True)
    sent = {}

    monkeypatch.setattr(service, "create_verification_code", lambda email, purpose: "654321", raising=True)

    def mock_send(email, code, purpose):
        sent["email"] = email
        sent["code"] = code
        sent["purpose"] = purpose
        return True

    monkeypatch.setattr(service, "send_verification_email", mock_send, raising=True)

    service.request_password_reset("alice@test.com")
    assert sent["email"] == "alice@test.com"
    assert sent["code"] == "654321"
    assert sent["purpose"] == "reset_password"


def test_complete_registration_invalid_code(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "consume_verification_code", lambda *args: False, raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        service.complete_registration("alice@test.com", "wrong", "pw")
    assert exc.value.status_code == 400


def test_complete_registration_success(monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock):
    monkeypatch.setattr(service, "consume_verification_code", lambda *args: True, raising=True)
    monkeypatch.setattr(service, "email_exists", lambda email: False, raising=True)

    user = User(id=1, username="alice", email="alice@test.com", password="x")
    monkeypatch.setattr(service, "create_user", lambda *args, **kwargs: user, raising=True)

    mock_token_pair = TokenPair(
        access_token="token-123",
        refresh_token="refresh-456",
        expires_in=3600,
        refresh_token_expires_in=604800,
    )
    monkeypatch.setattr(service, "create_token", lambda _: mock_token_pair, raising=True)

    result = service.complete_registration("alice@test.com", "123456", "pw")
    assert result.access_token == "token-123"
