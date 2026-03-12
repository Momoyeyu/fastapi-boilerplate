"""
Auth service — consolidated business logic for authentication.

Sections:
1. Verification codes (Redis)
2. Refresh tokens (Redis)
3. Token creation & login
4. Registration
5. Password reset
"""

import json
import secrets
import time
from functools import cache
from secrets import randbelow
from typing import Literal
from uuid import UUID

from jwt import PyJWT
from uuid6 import uuid7

from auth.dto import TokenPair
from auth.model import increment_used_count, validate_invitation_code
from common import erri
from common.email import send_verification_email
from common.utils import get_password_hash, validate_password, verify_password
from conf.config import settings
from conf.redis import get_redis
from tenant.service import create_user_with_tenant
from user.model import User, email_exists, get_user_by_email, get_user_by_identifier, update_user_password

# ---------------------------------------------------------------------------
# 1. Verification codes (Redis)
# ---------------------------------------------------------------------------

PurposeType = Literal["register", "reset_password"]

_VERIFICATION_PREFIX = "verification:"


def _make_key(email: str, purpose: PurposeType) -> str:
    return f"{_VERIFICATION_PREFIX}{email.lower()}:{purpose}"


def generate_code() -> str:
    return str(randbelow(900000) + 100000)


def create_verification_code(email: str, purpose: PurposeType) -> str:
    code = generate_code()
    key = _make_key(email, purpose)
    get_redis().setex(key, settings.verification_code_expire_seconds, code)
    return code


def consume_verification_code(email: str, code: str, purpose: PurposeType) -> bool:
    key = _make_key(email, purpose)
    r = get_redis()
    stored = r.get(key)
    if stored is None or stored != code:
        return False
    r.delete(key)
    return True


_INVITATION_PREFIX = "invitation_context:"


def store_invitation_context(email: str, invitation_code_id: UUID) -> None:
    key = f"{_INVITATION_PREFIX}{email.lower()}"
    get_redis().setex(key, settings.verification_code_expire_seconds, str(invitation_code_id))


def consume_invitation_context(email: str) -> UUID | None:
    key = f"{_INVITATION_PREFIX}{email.lower()}"
    r = get_redis()
    value = r.get(key)
    if value is None:
        return None
    r.delete(key)
    return UUID(value)


# ---------------------------------------------------------------------------
# 2. Refresh tokens (Redis)
#
# Key design:
# - refresh_token:{token} -> JSON {"user_id": "<uuid>", "username": "..."} with TTL
# - user_tokens:{user_id} -> Redis SET of active token strings (for bulk revocation)
# ---------------------------------------------------------------------------

_REFRESH_PREFIX = "refresh_token:"
_USER_TOKENS_PREFIX = "user_tokens:"


def generate_refresh_token() -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(32)


def create_refresh_token(user_id: UUID, username: str) -> str:
    """Create and store a new refresh token.

    Returns:
        The token string.
    """
    token = generate_refresh_token()
    data = json.dumps({"user_id": str(user_id), "username": username})
    ttl = settings.refresh_token_expire_seconds
    r = get_redis()
    r.set(f"{_REFRESH_PREFIX}{token}", data, ex=ttl)
    user_set_key = f"{_USER_TOKENS_PREFIX}{user_id}"
    r.sadd(user_set_key, token)
    # Refresh TTL on user set so it doesn't grow unbounded.
    # Set to 2x token TTL to cover tokens created at different times.
    r.expire(user_set_key, ttl * 2)
    return token


def validate_refresh_token(token: str) -> dict | None:
    """Validate a refresh token.

    Returns:
        Token data dict {"user_id": "<uuid>", "username": "..."} if valid, None otherwise.
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
    """Atomically rotate a refresh token using GETDEL + pipeline.

    Returns:
        A tuple of (new_token_string, user_data_dict) or None if invalid.
    """
    r = get_redis()

    # Atomically get-and-delete to prevent concurrent rotation
    old_key = f"{_REFRESH_PREFIX}{old_token}"
    data = r.getdel(old_key)
    if data is None:
        return None
    parsed = json.loads(data)

    # Pipeline the remaining operations
    new_token = generate_refresh_token()
    pipe = r.pipeline()
    pipe.srem(f"{_USER_TOKENS_PREFIX}{parsed['user_id']}", old_token)
    pipe.set(f"{_REFRESH_PREFIX}{new_token}", data, ex=settings.refresh_token_expire_seconds)
    pipe.sadd(f"{_USER_TOKENS_PREFIX}{parsed['user_id']}", new_token)
    pipe.execute()

    return new_token, parsed


def revoke_all_for_user(user_id: UUID) -> int:
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


# ---------------------------------------------------------------------------
# 3. Token creation & login
# ---------------------------------------------------------------------------


@cache
def _jwt() -> PyJWT:
    return PyJWT()


def create_access_token(username: str) -> tuple[str, int]:
    """Create a JWT access token for the user.

    Returns:
        A tuple of (access_token, expires_in).
    """
    now = int(time.time())
    expires_in = settings.jwt_expire_seconds
    payload = {"sub": username, "iat": now, "exp": now + expires_in}
    token = _jwt().encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_in


def create_token(user: User) -> TokenPair:
    """Create access and refresh tokens for the user.

    Returns:
        A TokenPair containing access_token, refresh_token, and expiration info.
    """
    if user.id is None:
        raise erri.internal("User ID is required for token creation")

    access_token, expires_in = create_access_token(user.username)
    refresh_token_str = create_refresh_token(user.id, user.username)

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token_str,
        expires_in=expires_in,
        refresh_token_expires_in=settings.refresh_token_expire_seconds,
    )


def refresh_tokens(refresh_token: str) -> TokenPair:
    """Refresh the access token using a refresh token.

    Implements Token Rotation: the old refresh token is revoked and a new one is issued.

    Returns:
        A new TokenPair with fresh access and refresh tokens.

    Raises:
        BusinessError: If the refresh token is invalid, expired, or revoked.
    """
    result = rotate_refresh_token(refresh_token)
    if not result:
        raise erri.unauthorized("Invalid or expired refresh token")

    new_token, user_data = result
    access_token, expires_in = create_access_token(user_data["username"])

    return TokenPair(
        access_token=access_token,
        refresh_token=new_token,
        expires_in=expires_in,
        refresh_token_expires_in=settings.refresh_token_expire_seconds,
    )


def revoke_token(refresh_token: str) -> bool:
    """Revoke a refresh token.

    Returns:
        True if the token was revoked, False if it was not found.
    """
    return revoke_refresh_token(refresh_token)


async def login_user(identifier: str, password: str) -> TokenPair:
    """Authenticate user and create tokens.

    Args:
        identifier: Email or username.
        password: Plain text password.

    Returns:
        A TokenPair containing access_token, refresh_token, and expiration info.
    """
    user = await get_user_by_identifier(identifier)
    if not user or user.id is None or not verify_password(password, user.hashed_password):
        raise erri.unauthorized("Invalid credentials")
    return create_token(user)


# ---------------------------------------------------------------------------
# 4. Registration
# ---------------------------------------------------------------------------


async def initiate_registration(email: str, password: str, invitation_code: str | None = None) -> None:
    """Initiate registration by sending a verification code.

    Args:
        email: User's email address.
        password: User's password (validated but not stored yet).
        invitation_code: Optional invitation code (required if configured).

    Raises:
        BusinessError: If email is already registered or invitation code is invalid.
    """
    if await email_exists(email):
        raise erri.conflict("Email already registered")

    invitation_code_id: UUID | None = None
    if settings.require_invitation_code:
        if not invitation_code:
            raise erri.bad_request("Invitation code is required")
        invitation = await validate_invitation_code(invitation_code)
        if not invitation or invitation.id is None:
            raise erri.bad_request("Invalid or expired invitation code")
        invitation_code_id = invitation.id

    code = create_verification_code(email, "register")
    await send_verification_email(email, code, "register")

    if invitation_code_id is not None:
        store_invitation_context(email, invitation_code_id)


async def complete_registration(email: str, code: str, password: str) -> TokenPair:
    """Complete registration after email verification.

    Args:
        email: User's email address.
        code: Verification code.
        password: User's password.

    Returns:
        A TokenPair for the newly created user.

    Raises:
        BusinessError: If verification fails or user creation fails.
    """
    if not consume_verification_code(email, code, "register"):
        raise erri.bad_request("Invalid or expired verification code")

    if await email_exists(email):
        raise erri.conflict("Email already registered")

    invitation_code_id = consume_invitation_context(email)

    validate_password(password)
    hashed = get_password_hash(password)

    username = f"user_{uuid7().hex[:12]}"
    tenant_name = f"workspace_{uuid7().hex[:12]}"

    try:
        user, _, _ = await create_user_with_tenant(
            username, hashed, email, tenant_name, invitation_code_id=invitation_code_id
        )
    except Exception:
        raise erri.internal("Create user failed") from None

    if invitation_code_id is not None:
        await increment_used_count(invitation_code_id)

    return create_token(user)


# ---------------------------------------------------------------------------
# 5. Password reset
# ---------------------------------------------------------------------------


async def request_password_reset(email: str) -> None:
    """Request password reset by sending a verification code.

    Args:
        email: User's email address.

    Note:
        Always returns success to prevent email enumeration.
    """
    if not await email_exists(email):
        return

    code = create_verification_code(email, "reset_password")
    await send_verification_email(email, code, "reset_password")


async def reset_password(email: str, code: str, new_password: str) -> bool:
    """Reset password after email verification.

    Args:
        email: User's email address.
        code: Verification code.
        new_password: New password.

    Returns:
        True if password was reset successfully.

    Raises:
        BusinessError: If verification fails.
    """
    if not consume_verification_code(email, code, "reset_password"):
        raise erri.bad_request("Invalid or expired verification code")

    validate_password(new_password)

    user = await get_user_by_email(email)
    if not user:
        raise erri.not_found("User not found")

    hashed = get_password_hash(new_password)
    result = await update_user_password(user.username, hashed)

    if result and user.id is not None:
        revoke_all_for_user(user.id)

    return result
