import hashlib
from unittest.mock import MagicMock

import pytest

from auth import password


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
