"""Unit tests for Redis-based refresh token service."""

from unittest.mock import patch

import pytest

from auth.refresh_token import (
    create_refresh_token,
    revoke_all_for_user,
    revoke_refresh_token,
    rotate_refresh_token,
    validate_refresh_token,
)


class FakePipeline:
    """Minimal pipeline mock that buffers and executes commands."""

    def __init__(self, redis):
        self._redis = redis
        self._commands = []

    def set(self, key, value, ex=None):
        self._commands.append(("set", key, value, ex))
        return self

    def srem(self, key, *members):
        self._commands.append(("srem", key, *members))
        return self

    def sadd(self, key, *members):
        self._commands.append(("sadd", key, *members))
        return self

    def execute(self):
        for cmd in self._commands:
            getattr(self._redis, cmd[0])(*cmd[1:])
        self._commands.clear()


class FakeRedis:
    """Minimal Redis mock for unit testing."""

    def __init__(self):
        self._store = {}
        self._sets = {}

    def set(self, key, value, ex=None):
        self._store[key] = value

    def get(self, key):
        return self._store.get(key)

    def getdel(self, key):
        return self._store.pop(key, None)

    def delete(self, key):
        self._store.pop(key, None)
        self._sets.pop(key, None)

    def sadd(self, key, *members):
        if key not in self._sets:
            self._sets[key] = set()
        for m in members:
            self._sets[key].add(m)

    def smembers(self, key):
        return self._sets.get(key, set()).copy()

    def srem(self, key, *members):
        if key in self._sets:
            for m in members:
                self._sets[key].discard(m)

    def pipeline(self):
        return FakePipeline(self)


@pytest.fixture
def fake_redis():
    fake = FakeRedis()
    with patch("auth.refresh_token.get_redis", return_value=fake):
        yield fake


def test_create_refresh_token(fake_redis):
    token = create_refresh_token(1, "alice")
    assert len(token) > 0
    # Token should be stored in Redis
    assert fake_redis.get(f"refresh_token:{token}") is not None
    # Token should be tracked in user set
    assert token in fake_redis.smembers("user_tokens:1")


def test_validate_refresh_token_success(fake_redis):
    token = create_refresh_token(1, "alice")
    data = validate_refresh_token(token)
    assert data is not None
    assert data["user_id"] == 1
    assert data["username"] == "alice"


def test_validate_refresh_token_invalid(fake_redis):
    assert validate_refresh_token("nonexistent") is None


def test_revoke_refresh_token_success(fake_redis):
    token = create_refresh_token(1, "alice")
    assert revoke_refresh_token(token) is True
    assert validate_refresh_token(token) is None
    assert token not in fake_redis.smembers("user_tokens:1")


def test_revoke_refresh_token_nonexistent(fake_redis):
    assert revoke_refresh_token("nonexistent") is False


def test_rotate_refresh_token_success(fake_redis):
    old_token = create_refresh_token(1, "alice")
    result = rotate_refresh_token(old_token)

    assert result is not None
    new_token, data = result
    assert new_token != old_token
    assert data["user_id"] == 1
    assert data["username"] == "alice"

    # Old token revoked
    assert validate_refresh_token(old_token) is None
    # New token valid
    assert validate_refresh_token(new_token) is not None


def test_rotate_refresh_token_invalid(fake_redis):
    assert rotate_refresh_token("nonexistent") is None


def test_revoke_all_for_user(fake_redis):
    t1 = create_refresh_token(1, "alice")
    t2 = create_refresh_token(1, "alice")
    t3 = create_refresh_token(2, "bob")

    count = revoke_all_for_user(1)
    assert count == 2

    # Alice's tokens revoked
    assert validate_refresh_token(t1) is None
    assert validate_refresh_token(t2) is None
    # Bob's token still valid
    assert validate_refresh_token(t3) is not None
