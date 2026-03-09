from unittest.mock import patch

import pytest

from auth.verification import (
    consume_invitation_context,
    consume_verification_code,
    create_verification_code,
    generate_code,
    store_invitation_context,
)


class FakeRedis:
    """Minimal Redis mock for testing."""

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
    with patch("auth.verification.get_redis", return_value=fake):
        yield fake


def test_generate_code_is_six_digits():
    for _ in range(100):
        code = generate_code()
        assert len(code) == 6
        assert code.isdigit()
        assert 100000 <= int(code) <= 999999


def test_create_verification_code_stores_in_redis(fake_redis):
    code = create_verification_code("Alice@Test.com", "register")
    assert len(code) == 6
    stored = fake_redis.get("verification:alice@test.com:register")
    assert stored == code


def test_consume_verification_code_success(fake_redis):
    code = create_verification_code("user@test.com", "register")
    assert consume_verification_code("user@test.com", code, "register") is True
    # Code should be deleted after consumption
    assert fake_redis.get("verification:user@test.com:register") is None


def test_consume_verification_code_wrong_code(fake_redis):
    create_verification_code("user@test.com", "register")
    assert consume_verification_code("user@test.com", "000000", "register") is False


def test_consume_verification_code_no_code(fake_redis):
    assert consume_verification_code("noone@test.com", "123456", "register") is False


def test_consume_verification_code_wrong_purpose(fake_redis):
    code = create_verification_code("user@test.com", "register")
    assert consume_verification_code("user@test.com", code, "reset_password") is False


def test_create_verification_code_overwrites_previous(fake_redis):
    code1 = create_verification_code("user@test.com", "register")
    code2 = create_verification_code("user@test.com", "register")
    # Old code should no longer work if different
    if code1 != code2:
        assert consume_verification_code("user@test.com", code1, "register") is False
    assert consume_verification_code("user@test.com", code2, "register") is True


def test_store_and_consume_invitation_context(fake_redis):
    store_invitation_context("Alice@Test.com", 42)
    assert consume_invitation_context("Alice@Test.com") == 42
    # Should be deleted after consumption
    assert consume_invitation_context("Alice@Test.com") is None


def test_consume_invitation_context_missing(fake_redis):
    assert consume_invitation_context("nobody@test.com") is None
