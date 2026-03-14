import bcrypt

from common import erri


def validate_password(password: str) -> None:
    """Validate password strength. Raises BusinessError if too weak."""
    if len(password) < 8:
        raise erri.bad_request("Password must be at least 8 characters")
    if not any(c.isupper() for c in password):
        raise erri.bad_request("Password must contain an uppercase letter")
    if not any(c.islower() for c in password):
        raise erri.bad_request("Password must contain a lowercase letter")
    if not any(c.isdigit() for c in password):
        raise erri.bad_request("Password must contain a digit")


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    """Verify a password against its bcrypt hash."""
    if hashed_password is None:
        return False
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
