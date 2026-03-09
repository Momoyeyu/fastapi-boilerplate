import redis as redis_lib

from conf.config import settings

_client: redis_lib.Redis | None = None


def get_redis() -> redis_lib.Redis:
    global _client
    if _client is None:
        _client = redis_lib.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )
    return _client


def close_redis() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
