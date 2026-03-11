from auth.password import get_password_hash, validate_password
from auth.token import TokenPair, create_token
from auth.verification import consume_verification_code, create_verification_code
from common import erri
from common.email import send_verification_email
from conf.config import settings
from user.model import email_exists


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

    invitation_code_id: int | None = None
    if settings.require_invitation_code:
        if not invitation_code:
            raise erri.bad_request("Invitation code is required")
        from invitation.model import validate_invitation_code

        invitation = await validate_invitation_code(invitation_code)
        if not invitation or invitation.id is None:
            raise erri.bad_request("Invalid or expired invitation code")
        invitation_code_id = invitation.id

    code = create_verification_code(email, "register")
    await send_verification_email(email, code, "register")

    if invitation_code_id is not None:
        from auth.verification import store_invitation_context

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

    from auth.verification import consume_invitation_context

    invitation_code_id = consume_invitation_context(email)

    validate_password(password)
    hashed = get_password_hash(password)
    username = email.split("@")[0]
    tenant_name = f"{username}'s workspace"

    from tenant.service import create_user_with_tenant

    try:
        user, _, _ = await create_user_with_tenant(
            username, hashed, email, tenant_name, invitation_code_id=invitation_code_id
        )
    except Exception:
        raise erri.internal("Create user failed")

    if invitation_code_id is not None:
        from invitation.model import increment_used_count

        await increment_used_count(invitation_code_id)

    return create_token(user)
