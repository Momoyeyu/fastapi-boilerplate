import hashlib

from auth.verification import consume_verification_code, create_verification_code
from common import erri
from common.email import send_verification_email
from conf.config import settings
from user.model import email_exists


def get_password_hash(password: str) -> str:
    """Hash a password with the configured salt."""
    return hashlib.sha512((password + settings.password_salt).encode("utf-8")).hexdigest()


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

    from user.model import get_user_by_email, update_user_password

    user = await get_user_by_email(email)
    if not user:
        raise erri.not_found("User not found")

    encrypted_password = get_password_hash(new_password)
    return await update_user_password(user.username, encrypted_password)
