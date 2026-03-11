"""
Redis-based refresh token service.

Key design:
- refresh_token:{token} → JSON {"user_id": N, "username": "..."} with TTL
- user_tokens:{user_id} → Redis SET of active token strings (for bulk revocation)
"""

import json
import secrets

from conf.config import settings
from conf.redis import get_redis

_REFRESH_PREFIX = "refresh_token:"
_USER_TOKENS_PREFIX = "user_tokens:"


def generate_refresh_token() -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(32)


def create_refresh_token(user_id: int, username: str) -> str:
    """Create and store a new refresh token.

    Returns:
        The token string.
    """
    token = generate_refresh_token()
    data = json.dumps({"user_id": user_id, "username": username})
    r = get_redis()
    r.set(f"{_REFRESH_PREFIX}{token}", data, ex=settings.refresh_token_expire_seconds)
    r.sadd(f"{_USER_TOKENS_PREFIX}{user_id}", token)
    return token


def validate_refresh_token(token: str) -> dict | None:
    """Validate a refresh token.

    Returns:
        Token data dict {"user_id": N, "username": "..."} if valid, None otherwise.
    """
    r = get_redis()
    data = r.get(f"{_REFRESH_PREFIX}{token}")
    if data is None:
        return None
    return json.loads(data)


def revoke_refresh_token(token: str) -> bool:
    """Revoke a refresh token.

    Returns:
        True if the token was found and revoked, False otherwise.
    """
    r = get_redis()
    data = r.get(f"{_REFRESH_PREFIX}{token}")
    if data is None:
        return False
    parsed = json.loads(data)
    r.delete(f"{_REFRESH_PREFIX}{token}")
    r.srem(f"{_USER_TOKENS_PREFIX}{parsed['user_id']}", token)
    return True


def rotate_refresh_token(old_token: str) -> tuple[str, dict] | None:
    """Atomically rotate a refresh token.

    Validates and revokes the old token, then creates a new one.

    Returns:
        A tuple of (new_token_string, user_data_dict) or None if invalid.
    """
    r = get_redis()
    data = r.get(f"{_REFRESH_PREFIX}{old_token}")
    if data is None:
        return None
    parsed = json.loads(data)

    # Revoke old token
    r.delete(f"{_REFRESH_PREFIX}{old_token}")
    r.srem(f"{_USER_TOKENS_PREFIX}{parsed['user_id']}", old_token)

    # Create new token
    new_token = generate_refresh_token()
    r.set(f"{_REFRESH_PREFIX}{new_token}", data, ex=settings.refresh_token_expire_seconds)
    r.sadd(f"{_USER_TOKENS_PREFIX}{parsed['user_id']}", new_token)

    return new_token, parsed


def revoke_all_for_user(user_id: int) -> int:
    """Revoke all refresh tokens for a user.

    Returns:
        The number of tokens revoked.
    """
    r = get_redis()
    tokens = r.smembers(f"{_USER_TOKENS_PREFIX}{user_id}")
    for token in tokens:
        r.delete(f"{_REFRESH_PREFIX}{token}")
    r.delete(f"{_USER_TOKENS_PREFIX}{user_id}")
    return len(tokens)
