import pytest

from auth import password


def test_get_password_hash_returns_bcrypt_hash():
    """Test that get_password_hash returns a valid bcrypt hash."""
    hashed = password.get_password_hash("my_secret")
    assert hashed.startswith("$2")
    assert len(hashed) == 60


def test_get_password_hash_different_each_time():
    """Bcrypt generates random salt, so hashes differ."""
    h1 = password.get_password_hash("same")
    h2 = password.get_password_hash("same")
    assert h1 != h2


def test_verify_password_correct():
    hashed = password.get_password_hash("secret")
    assert password.verify_password("secret", hashed) is True


def test_verify_password_incorrect():
    hashed = password.get_password_hash("secret")
    assert password.verify_password("wrong", hashed) is False


async def test_request_password_reset_sends_code(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        password, "email_exists", lambda *a, **k: __import__("asyncio").coroutine(lambda: True)(), raising=True
    )
    sent = {}

    monkeypatch.setattr(password, "create_verification_code", lambda email, purpose: "654321", raising=True)

    async def async_mock_send(email, code, purpose):
        sent["email"] = email
        sent["code"] = code
        sent["purpose"] = purpose
        return True

    monkeypatch.setattr(password, "send_verification_email", async_mock_send, raising=True)

    async def mock_email_exists(email):
        return True

    monkeypatch.setattr(password, "email_exists", mock_email_exists, raising=True)

    await password.request_password_reset("alice@test.com")
    assert sent["email"] == "alice@test.com"
    assert sent["code"] == "654321"
    assert sent["purpose"] == "reset_password"
