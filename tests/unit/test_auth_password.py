import hashlib
from unittest.mock import MagicMock

import pytest

from auth import password


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
    monkeypatch.setattr(password, "settings", mock)
    return mock


def test_get_password_hash_uses_salt(mock_settings: MagicMock):
    pw = "pw"
    expected = hashlib.sha512((pw + "salt").encode("utf-8")).hexdigest()
    assert password.get_password_hash(pw) == expected


async def test_request_password_reset_sends_code(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(password, "email_exists", async_return(True), raising=True)
    sent = {}

    monkeypatch.setattr(password, "create_verification_code", lambda email, purpose: "654321", raising=True)

    def mock_send(email, code, purpose):
        sent["email"] = email
        sent["code"] = code
        sent["purpose"] = purpose
        return True

    async def async_mock_send(email, code, purpose):
        return mock_send(email, code, purpose)

    monkeypatch.setattr(password, "send_verification_email", async_mock_send, raising=True)

    await password.request_password_reset("alice@test.com")
    assert sent["email"] == "alice@test.com"
    assert sent["code"] == "654321"
    assert sent["purpose"] == "reset_password"
