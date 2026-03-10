import resend
from loguru import logger

from conf.config import settings


def _init_resend() -> bool:
    """Initialize Resend API key. Returns False if not configured."""
    key = settings.resend_api_key.get_secret_value()
    if not key:
        return False
    resend.api_key = key
    return True


def send_verification_email(email: str, code: str, purpose: str) -> bool:
    """Send a verification code email via Resend.

    Args:
        email: Recipient email address.
        code: 6-digit verification code.
        purpose: "register" or "reset_password".

    Returns:
        True if sent successfully, False otherwise.
    """
    if not _init_resend():
        logger.warning("Resend API key not configured, skipping email send")
        return False

    if purpose == "register":
        subject = "Your Registration Code"
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Welcome</h2>
            <p>Your registration verification code is:</p>
            <p style="font-size: 32px; font-weight: bold; color: #4F46E5; letter-spacing: 4px;">{code}</p>
            <p>This code will expire in 5 minutes.</p>
            <p style="color: #666; font-size: 12px;">If you did not request this, please ignore this email.</p>
        </div>
        """
    elif purpose == "reset_password":
        subject = "Password Reset Code"
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Password Reset Request</h2>
            <p>Your password reset verification code is:</p>
            <p style="font-size: 32px; font-weight: bold; color: #4F46E5; letter-spacing: 4px;">{code}</p>
            <p>This code will expire in 5 minutes.</p>
            <p style="color: #666; font-size: 12px;">If you did not request this, please ignore this email.</p>
        </div>
        """
    else:
        subject = "Verification Code"
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <p>Your verification code is:</p>
            <p style="font-size: 32px; font-weight: bold; color: #4F46E5; letter-spacing: 4px;">{code}</p>
            <p>This code will expire in 5 minutes.</p>
        </div>
        """

    try:
        result = resend.Emails.send(
            {
                "from": settings.email_from,
                "to": email,
                "subject": subject,
                "html": html_content,
            }
        )
        logger.info(f"Verification email sent to {email}, id: {result.id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send verification email to {email}: {e}")
        return False


def send_email(to_email: str, subject: str, html_content: str) -> bool:
    """Send a custom email via Resend.

    Args:
        to_email: Recipient email address.
        subject: Email subject.
        html_content: HTML body.

    Returns:
        True if sent successfully, False otherwise.
    """
    if not _init_resend():
        logger.warning("Resend API key not configured, skipping email send")
        return False

    try:
        result = resend.Emails.send(
            {
                "from": settings.email_from,
                "to": to_email,
                "subject": subject,
                "html": html_content,
            }
        )
        logger.info(f"Email sent to {to_email}, id: {result.id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False
