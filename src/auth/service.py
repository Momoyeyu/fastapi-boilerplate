import hashlib
import time
from dataclasses import dataclass
from functools import cache

from jwt import PyJWT

from auth.model import create_refresh_token, revoke_refresh_token, rotate_refresh_token
from common import erri
from conf.config import settings
from user.model import User, get_user


@cache
def _jwt() -> PyJWT:
    return PyJWT()


@dataclass
class TokenPair:
    """A pair of access and refresh tokens."""

    access_token: str
    refresh_token: str
    expires_in: int
    refresh_token_expires_in: int


def get_password_hash(password: str) -> str:
    """Hash a password with the configured salt."""
    return hashlib.sha512((password + settings.password_salt).encode("utf-8")).hexdigest()


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
    refresh_token_obj = create_refresh_token(user.id, user.username)

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token_obj.token,
        expires_in=expires_in,
        refresh_token_expires_in=settings.refresh_token_expire_seconds,
    )


def refresh_tokens(refresh_token: str) -> TokenPair:
    """Refresh the access token using a refresh token.

    Implements Token Rotation: the old refresh token is revoked and a new one is issued.
    Uses a database transaction to ensure atomicity.

    Returns:
        A new TokenPair with fresh access and refresh tokens.

    Raises:
        BusinessError: If the refresh token is invalid, expired, or revoked.
    """
    new_refresh_token = rotate_refresh_token(refresh_token)
    if not new_refresh_token:
        raise erri.unauthorized("Invalid or expired refresh token")

    access_token, expires_in = create_access_token(new_refresh_token.username)

    return TokenPair(
        access_token=access_token,
        refresh_token=new_refresh_token.token,
        expires_in=expires_in,
        refresh_token_expires_in=settings.refresh_token_expire_seconds,
    )


def revoke_token(refresh_token: str) -> bool:
    """Revoke a refresh token.

    Returns:
        True if the token was revoked, False if it was not found.
    """
    return revoke_refresh_token(refresh_token)


def login_user(username: str, password: str) -> TokenPair:
    """Authenticate user and create tokens.

    Returns:
        A TokenPair containing access_token, refresh_token, and expiration info.
    """
    user = get_user(username)
    encrypted_password = get_password_hash(password)
    if not user or user.password != encrypted_password or user.id is None:
        raise erri.unauthorized("Invalid credentials")
    return create_token(user)
