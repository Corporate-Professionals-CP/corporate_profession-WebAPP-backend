import logging
import asyncio
import resend
from fastapi import HTTPException, status
from app.core.config import settings

logger = logging.getLogger(__name__)


resend.api_key = settings.RESEND_API_KEY

async def _send_email_resend(to_email: str, to_name: str, subject: str, text: str, html: str):
    try:
        await asyncio.to_thread(resend.Emails.send, {
            "from": f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>",
            "to": [to_email],
            "subject": subject,
            "text": text,
            "html": html
        })
        logger.info(f"Email sent to {to_email}")

    except Exception as e:
        logger.error(f"Email sending failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service temporarily unavailable"
        )

async def send_verification_email(email: str, name: str, token: str) -> None:
    subject = "Verify Your Email"
    text = f"Hello {name},\n\nPlease verify your email: {settings.FRONTEND_URL}/verify-email?token={token}"
    html = f"<h3>Hello {name},</h3><p>Please <a href='{settings.FRONTEND_URL}/verify-email?token={token}'>verify your email</a>.</p>"
    await _send_email_resend(email, name, subject, text, html)

async def send_password_reset_email(email: str, name: str, token: str) -> None:
    subject = "Password Reset Instructions"
    text = f"Hello {name},\n\nReset your password: {settings.FRONTEND_URL}/reset-password?token={token}"
    html = f"<h3>Hello {name},</h3><p><a href='{settings.FRONTEND_URL}/reset-password?token={token}'>Reset your password here</a>.</p>"
    await _send_email_resend(email, name, subject, text, html)

