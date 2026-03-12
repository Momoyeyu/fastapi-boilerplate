"""Email service (Resend)."""

import asyncio
from html import escape

import resend
from loguru import logger

from conf.config import settings

_TEMPLATES = {
    "register": (
        "Your Registration Code",
        "Welcome",
        "Your registration verification code is:",
        "If you did not request this, please ignore this email.",
    ),
    "reset_password": (
        "Password Reset Code",
        "Password Reset Request",
        "Your password reset verification code is:",
        "If you did not request this, please ignore this email. Your password will not be changed.",
    ),
}
_DEFAULT_TEMPLATE = ("Verification Code", "", "Your verification code is:", "")


def _build_html(code: str, title: str, message: str, footer: str) -> str:
    safe_code = escape(code)
    title_html = f"<h2>{title}</h2>" if title else ""
    footer_html = f'<p style="color: #666; font-size: 12px;">{footer}</p>' if footer else ""
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        {title_html}
        <p>{message}</p>
        <p style="font-size: 32px; font-weight: bold; color: #4F46E5; letter-spacing: 4px;">{safe_code}</p>
        <p>This code will expire in 5 minutes.</p>
        {footer_html}
    </div>
    """


async def send_email(to_email: str, subject: str, html: str) -> bool:
    key = settings.resend_api_key.get_secret_value()
    if not key:
        logger.warning("Resend API key not configured, skipping email send")
        return False
    resend.api_key = key
    try:
        payload = {"from": settings.email_from, "to": to_email, "subject": subject, "html": html}
        result = await asyncio.to_thread(resend.Emails.send, payload)
        logger.info(f"Email sent to {to_email}, id: {result.id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


async def send_verification_email(email: str, code: str, purpose: str) -> bool:
    """Send a verification code email. Supports register / reset_password templates."""
    logger.debug(f"Verification code for {email} ({purpose}): {code}")
    subject, title, message, footer = _TEMPLATES.get(purpose, _DEFAULT_TEMPLATE)
    prefix = f"{settings.app_name} - " if settings.app_name else ""
    return await send_email(email, f"{prefix}{subject}", _build_html(code, title, message, footer))
