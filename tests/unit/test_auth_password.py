import pytest

from auth import service
from common import erri
from common.resp import Code
from common.utils import get_password_hash, validate_password, verify_password


def test_validate_password_success():
    validate_password("Abcdefg1")  # should not raise


@pytest.mark.parametrize(
    "pw, expected_msg",
    [
        ("Short1A", "at least 8 characters"),
        ("alllowercase1", "uppercase letter"),
        ("ALLUPPERCASE1", "lowercase letter"),
        ("NoDigitsHere", "digit"),
    ],
)
def test_validate_password_rejects_weak(pw, expected_msg):
    with pytest.raises(erri.BusinessError) as exc:
        validate_password(pw)
    assert exc.value.code == Code.BAD_REQUEST
    assert expected_msg in exc.value.message


def test_get_password_hash_returns_bcrypt_hash():
    """Test that get_password_hash returns a valid bcrypt hash."""
    hashed = get_password_hash("my_secret")
    assert hashed.startswith("$2")
    assert len(hashed) == 60


def test_get_password_hash_different_each_time():
    """Bcrypt generates random salt, so hashes differ."""
    h1 = get_password_hash("same")
    h2 = get_password_hash("same")
    assert h1 != h2


def test_verify_password_correct():
    hashed = get_password_hash("secret")
    assert verify_password("secret", hashed) is True


def test_verify_password_incorrect():
    hashed = get_password_hash("secret")
    assert verify_password("wrong", hashed) is False


async def test_request_password_reset_sends_code(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        service, "email_exists", lambda *a, **k: __import__("asyncio").coroutine(lambda: True)(), raising=True
    )
    sent = {}

    monkeypatch.setattr(service, "create_verification_code", lambda email, purpose: "654321", raising=True)

    async def async_mock_send(email, code, purpose):
        sent["email"] = email
        sent["code"] = code
        sent["purpose"] = purpose
        return True

    monkeypatch.setattr(service, "send_verification_email", async_mock_send, raising=True)

    async def mock_email_exists(email):
        return True

    monkeypatch.setattr(service, "email_exists", mock_email_exists, raising=True)

    await service.request_password_reset("alice@test.com")
    assert sent["email"] == "alice@test.com"
    assert sent["code"] == "654321"
    assert sent["purpose"] == "reset_password"
