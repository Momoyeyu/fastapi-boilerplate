import hashlib
import time
from dataclasses import dataclass
from functools import cache

from jwt import PyJWT

from auth.model import create_refresh_token, revoke_refresh_token, rotate_refresh_token
from auth.verification import consume_verification_code, create_verification_code
from common import erri
from common.email import send_verification_email
from conf.config import settings
from user.model import User, create_user, email_exists, get_user_by_identifier


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


def login_user(identifier: str, password: str) -> TokenPair:
    """Authenticate user and create tokens.

    Args:
        identifier: Email or username.
        password: Plain text password.

    Returns:
        A TokenPair containing access_token, refresh_token, and expiration info.
    """
    user = get_user_by_identifier(identifier)
    encrypted_password = get_password_hash(password)
    if not user or user.password != encrypted_password or user.id is None:
        raise erri.unauthorized("Invalid credentials")
    return create_token(user)


def initiate_registration(email: str, password: str, invitation_code: str | None = None) -> None:
    """Initiate registration by sending a verification code.

    Args:
        email: User's email address.
        password: User's password (validated but not stored yet).
        invitation_code: Optional invitation code (required if configured).

    Raises:
        BusinessError: If email is already registered or invitation code is invalid.
    """
    if email_exists(email):
        raise erri.conflict("Email already registered")

    invitation_code_id: int | None = None
    if settings.require_invitation_code:
        if not invitation_code:
            raise erri.bad_request("Invitation code is required")
        from invitation.model import validate_invitation_code

        invitation = validate_invitation_code(invitation_code)
        if not invitation or invitation.id is None:
            raise erri.bad_request("Invalid or expired invitation code")
        invitation_code_id = invitation.id

    code = create_verification_code(email, "register")
    send_verification_email(email, code, "register")

    if invitation_code_id is not None:
        from auth.verification import store_invitation_context

        store_invitation_context(email, invitation_code_id)


def complete_registration(email: str, code: str, password: str) -> TokenPair:
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

    if email_exists(email):
        raise erri.conflict("Email already registered")

    from auth.verification import consume_invitation_context

    invitation_code_id = consume_invitation_context(email)

    encrypted_password = get_password_hash(password)
    username = email.split("@")[0]
    user = create_user(username, encrypted_password, email, invitation_code_id=invitation_code_id)
    if not user or user.id is None:
        raise erri.internal("Create user failed")

    if invitation_code_id is not None:
        from invitation.model import increment_used_count

        increment_used_count(invitation_code_id)

    return create_token(user)


def request_password_reset(email: str) -> None:
    """Request password reset by sending a verification code.

    Args:
        email: User's email address.

    Note:
        Always returns success to prevent email enumeration.
    """
    if not email_exists(email):
        return

    code = create_verification_code(email, "reset_password")
    send_verification_email(email, code, "reset_password")


def reset_password(email: str, code: str, new_password: str) -> bool:
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

    from user.model import get_user_by_email, update_user_password

    user = get_user_by_email(email)
    if not user:
        raise erri.not_found("User not found")

    encrypted_password = get_password_hash(new_password)
    return update_user_password(user.username, encrypted_password)
