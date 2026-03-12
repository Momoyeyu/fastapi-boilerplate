import secrets
from datetime import UTC, datetime, timedelta, timezone
from html import escape
from uuid import UUID

from uuid6 import uuid7

from auth.dto import TokenPair
from auth.service import create_token
from common import erri
from common.email import send_email
from common.utils import get_password_hash, validate_password
from conf.config import settings
from tenant.model import (
    create_tenant_invitation,
    create_user_tenant,
    get_invitation_by_token,
    get_pending_invitation_by_email_and_tenant,
    get_tenant,
    get_user_tenant,
    update_invitation_status,
)
from tenant.service import create_user_for_tenant
from user.model import email_exists, get_user_by_email


def _build_invite_html(tenant_name: str, invite_url: str) -> str:
    safe_name = escape(tenant_name)
    safe_url = escape(invite_url, quote=True)
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2>You're Invited</h2>
        <p>You have been invited to join <strong>{safe_name}</strong>.</p>
        <p>Click the link below to accept the invitation and set up your account:</p>
        <p><a href="{safe_url}"
              style="display: inline-block; padding: 12px 24px; background-color: #4F46E5;
                     color: #fff; text-decoration: none; border-radius: 6px;">
            Accept Invitation
        </a></p>
        <p style="color: #666; font-size: 12px;">
            This invitation will expire in 7 days. If you did not expect this, please ignore this email.
        </p>
    </div>
    """


def _build_added_html(tenant_name: str) -> str:
    safe_name = escape(tenant_name)
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2>You've Been Added to a Tenant</h2>
        <p>You have been added to <strong>{safe_name}</strong>.</p>
        <p>Log in to your account to access the tenant.</p>
    </div>
    """


async def _send_invite_email(email: str, tenant_name: str, invite_url: str) -> bool:
    prefix = f"{settings.app_name} - " if settings.app_name else ""
    subject = f"{prefix}You're invited to join {tenant_name}"
    return await send_email(email, subject, _build_invite_html(tenant_name, invite_url))


async def _send_added_email(email: str, tenant_name: str) -> bool:
    prefix = f"{settings.app_name} - " if settings.app_name else ""
    subject = f"{prefix}You've been added to {tenant_name}"
    return await send_email(email, subject, _build_added_html(tenant_name))


async def invite_user_to_tenant(inviter_id: UUID, tenant_id: UUID, email: str, role: str) -> dict:
    """Invite a user to join a tenant by email.

    If the email is already registered, the user is directly added to the tenant.
    Otherwise, a pending invitation with a token is created and sent via email.
    """
    if role not in ("member", "admin"):
        raise erri.bad_request("Role must be 'member' or 'admin'")

    user_tenant = await get_user_tenant(inviter_id, tenant_id)
    if not user_tenant:
        raise erri.not_found("Not a member of this tenant")
    if user_tenant.user_role not in ("owner", "admin"):
        raise erri.forbidden("Only owner or admin can invite users")

    tenant = await get_tenant(tenant_id)
    if not tenant:
        raise erri.not_found("Tenant not found")

    email = email.lower()

    existing = await get_pending_invitation_by_email_and_tenant(email, tenant_id)
    if existing:
        raise erri.conflict("Invitation already pending for this email")

    user = await get_user_by_email(email)
    if user:
        if await get_user_tenant(user.id, tenant_id):
            raise erri.conflict("User is already a member of this tenant")
        await create_user_tenant(user.id, tenant_id, user_role=role)
        await _send_added_email(email, tenant.name)
        return {"flow": "existing_user"}

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.invitation_token_expire_seconds)
    await create_tenant_invitation(tenant_id, email, role, inviter_id, token, expires_at)
    invite_url = f"{settings.frontend_url}/invite/accept?token={token}"
    await _send_invite_email(email, tenant.name, invite_url)
    return {"flow": "new_user"}


async def accept_invitation(token: str, password: str) -> TokenPair:
    """Accept a tenant invitation, create an account, and join the tenant."""
    invitation = await get_invitation_by_token(token)
    if not invitation:
        raise erri.bad_request("Invalid or expired invitation token")

    expires = invitation.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        raise erri.bad_request("Invitation has expired")

    if await email_exists(invitation.email):
        raise erri.conflict("Email already registered")

    validate_password(password)
    hashed = get_password_hash(password)
    username = f"user_{uuid7().hex[:12]}"

    try:
        user, _ = await create_user_for_tenant(
            username, hashed, invitation.email, invitation.tenant_id, invitation.role
        )
    except Exception:
        raise erri.internal("Failed to create user") from None

    await update_invitation_status(invitation.id, "accepted")
    return create_token(user)
