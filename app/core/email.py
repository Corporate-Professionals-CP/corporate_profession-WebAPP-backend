import logging
import asyncio
import resend
import random
import string
from fastapi import HTTPException, status
from app.core.config import settings

logger = logging.getLogger(__name__)


resend.api_key = settings.RESEND_API_KEY

async def generate_otp() -> str:
    """Generate a 6-digit numeric OTP"""
    return ''.join(random.choices(string.digits, k=6))

async def _send_email_resend(to_email: str, to_name: str, subject: str, text: str, html: str):
    logger.info(f"Resend API key: {settings.RESEND_API_KEY}")
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
    otp = await generate_otp()
    
    # Store the OTP in the user's record (we'll use profile_preferences field)
    # This is a temporary solution - in production, consider a dedicated OTP storage
    
    text = f"Hello {name},\n\nYour verification code is: {otp}\n\nEnter this code to verify your email."
    html = f"""
        <h3>Hello {name},</h3>
        <p>Your verification code is: <strong>{otp}</strong></p>
        <p>Enter this code to verify your email.</p>
    """
    
    # We'll return the OTP to store it in the user record
    return otp, await _send_email_resend(email, name, subject, text, html)

async def send_password_reset_email(email: str, name: str, token: str) -> None:
    subject = "Password Reset Instructions"
    text = f"Hello {name},\n\nReset your password: {settings.FRONTEND_URL}/reset-password?token={token}"
    html = f"<h3>Hello {name},</h3><p><a href='{settings.FRONTEND_URL}/reset-password?token={token}'>Reset your password here</a>.</p>"
    await _send_email_resend(email, name, subject, text, html)

