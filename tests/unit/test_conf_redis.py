from unittest.mock import MagicMock, patch

from conf import redis as redis_module
from conf.redis import clear_redis, get_redis


def test_get_redis_creates_client(monkeypatch):
    monkeypatch.setattr(redis_module, "_client", None)
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_cls.return_value = mock_instance

    with patch("conf.redis.coredis.Redis", mock_cls):
        result = get_redis()

    assert result is mock_instance
    mock_cls.assert_called_once()
    monkeypatch.setattr(redis_module, "_client", None)


def test_get_redis_returns_existing_client(monkeypatch):
    existing = MagicMock()
    monkeypatch.setattr(redis_module, "_client", existing)

    result = get_redis()

    assert result is existing
    monkeypatch.setattr(redis_module, "_client", None)


def test_clear_redis_resets_client(monkeypatch):
    mock_client = MagicMock()
    monkeypatch.setattr(redis_module, "_client", mock_client)

    clear_redis()

    assert redis_module._client is None


def test_clear_redis_noop_when_none(monkeypatch):
    monkeypatch.setattr(redis_module, "_client", None)

    clear_redis()  # should not raise

    assert redis_module._client is None
