# app/core/email.py
from mailjet_rest import Client as MailjetClient
from fastapi import HTTPException, status
import logging
from typing import Dict, Any
import asyncio

from app.core.config import settings

# Initialize Mailjet client
mailjet = MailjetClient(
    auth=(settings.MAILJET_API_KEY, settings.MAILJET_SECRET_KEY),
    version='v3.1'
)

async def _send_email(data: Dict[str, Any]) -> None:
    """Base function for sending emails through Mailjet"""
    try:
        response = await asyncio.to_thread(mailjet.send.create, data=data)
        if response.status_code != 200:
            logging.error(f"Mailjet API error: {response.status_code} - {response.text}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send email"
            )
    except Exception as e:
        logging.error(f"Email sending failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service temporarily unavailable"
        )

async def send_verification_email(email: str, name: str, token: str) -> None:
    """Send email verification link"""
    if not settings.VERIFICATION_TEMPLATE_ID:
        raise ValueError("Verification template ID not configured")

    data = {
        'Messages': [{
            "From": {
                "Email": settings.EMAILS_FROM_EMAIL,
                "Name": settings.EMAILS_FROM_NAME
            },
            "To": [{"Email": email, "Name": name}],
            "TemplateID": settings.VERIFICATION_TEMPLATE_ID,
            "TemplateLanguage": True,
            "Variables": {
                "name": name,
                "verification_link": f"{settings.FRONTEND_URL}/verify-email?token={token}"
            }
        }]
    }
    await _send_email(data)

async def send_password_reset_email(email: str, name: str, token: str) -> None:
    """Send password reset instructions"""
    if not settings.PASSWORD_RESET_TEMPLATE_ID:
        raise ValueError("Password reset template ID not configured")

    data = {
        'Messages': [{
            "From": {
                "Email": settings.EMAILS_FROM_EMAIL,
                "Name": settings.EMAILS_FROM_NAME
            },
            "To": [{"Email": email, "Name": name}],
            "TemplateID": settings.PASSWORD_RESET_TEMPLATE_ID,
            "TemplateLanguage": True,
            "Variables": {
                "name": name,
                "reset_link": f"{settings.FRONTEND_URL}/reset-password?token={token}"
            }
        }]
    }
    await _send_email(data)
