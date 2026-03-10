from auth.password import get_password_hash
from auth.token import TokenPair, create_token
from auth.verification import consume_verification_code, create_verification_code
from common import erri
from common.email import send_verification_email
from conf.config import settings
from user.model import create_user, email_exists


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
