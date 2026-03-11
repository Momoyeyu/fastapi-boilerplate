import bcrypt

from auth.verification import consume_verification_code, create_verification_code
from common import erri
from common.email import send_verification_email
from user.model import email_exists


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


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

    from auth.refresh_token import revoke_all_for_user
    from user.model import get_user_by_email, update_user_password

    user = await get_user_by_email(email)
    if not user:
        raise erri.not_found("User not found")

    hashed = get_password_hash(new_password)
    result = await update_user_password(user.username, hashed)

    if result and user.id is not None:
        revoke_all_for_user(user.id)

    return result
