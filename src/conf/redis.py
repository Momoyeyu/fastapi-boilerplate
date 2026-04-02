import threading

import coredis

from conf.config import settings

_client: coredis.Redis | None = None
_lock = threading.Lock()


def get_redis() -> coredis.Redis:
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = coredis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    db=settings.redis_db,
                    decode_responses=True,
                )
    return _client


def clear_redis() -> None:
    """Clear the global reference (call after the async context manager exits)."""
    global _client
    with _lock:
        _client = None
