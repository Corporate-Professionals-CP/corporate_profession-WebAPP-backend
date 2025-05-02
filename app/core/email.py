from mailjet_rest import Client as MailjetClient
from fastapi import HTTPException, status
import logging
from typing import Dict, Any
import asyncio
import os

import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

from app.core.config import settings

# Initialize Mailjet client
mailjet = MailjetClient(
    auth=(settings.MAILJET_API_KEY, settings.MAILJET_SECRET_KEY),
    version='v3.1'
)

async def _send_email(data: Dict[str, Any]) -> None:
    """Base function for sending emails through Mailjet with enhanced test logging"""
    try:
        # Enhanced environment check that works with both os.getenv and settings
        is_testing = (
            os.getenv("ENVIRONMENT") == "testing" or 
            getattr(settings, "ENVIRONMENT", "") == "testing"
        )

        if is_testing:
            # Extract key email components for cleaner logging
            to_email = data['Messages'][0]['To'][0]['Email']
            subject = data['Messages'][0]['Subject']
            
            # Extract token from both TextPart and HTMLPart for visibility
            text_content = data['Messages'][0].get('TextPart', '')
            html_content = data['Messages'][0].get('HTMLPart', '')
            
            # Token extraction logic
            token = None
            if 'token=' in text_content:
                token = text_content.split('token=')[1].split()[0]  # Get first word after token=
            elif 'token=' in html_content:
                token = html_content.split('token=')[1].split('"')[0]  # Get value before next quote
            
            # Structured test logging
            logger.info(
                "\n" + "="*40 + "\n" +
                "TEST MODE: Email would be sent\n"
                f"To: {to_email}\n"
                f"Subject: {subject}\n" +
                (f"Token: {token}\n" if token else "No token found\n") +
                "="*40 + "\n"
            )
            
            # For debugging during development
            logger.debug(f"Full email data: {data}")
            return

        # Production email sending
        response = await asyncio.to_thread(mailjet.send.create, data=data)
        
        if response.status_code != 200:
            error_msg = f"Mailjet API error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send email"
            )
            
        logger.info(f"Email successfully sent to {data['Messages'][0]['To'][0]['Email']}")

    except Exception as e:
        error_msg = f"Email sending failed: {str(e)}"
        logger.error(error_msg, exc_info=True)  # Include stack trace
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service temporarily unavailable"
        ) from e

async def send_verification_email(email: str, name: str, token: str) -> None:
    """Send email verification link (simplified for testing)"""
    data = {
        'Messages': [{
            "From": {
                "Email": settings.EMAILS_FROM_EMAIL,
                "Name": settings.EMAILS_FROM_NAME
            },
            "To": [{"Email": email, "Name": name}],
            "Subject": "Verify Your Email",
            "TextPart": f"Hello {name},\n\nPlease verify your email by clicking this link: {settings.FRONTEND_URL}/verify-email?token={token}",
            "HTMLPart": f"<h3>Hello {name},</h3><p>Please verify your email by <a href='{settings.FRONTEND_URL}/verify-email?token={token}'>clicking here</a></p>"
        }]
    }
    await _send_email(data)

async def send_password_reset_email(email: str, name: str, token: str) -> None:
    """Send password reset instructions"""
    # In testing environment, the token will automatically appear in server logs
    # through the _send_email function's logging
    
    data = {
        'Messages': [{
            "From": {
                "Email": settings.EMAILS_FROM_EMAIL,
                "Name": settings.EMAILS_FROM_NAME
            },
            "To": [{"Email": email, "Name": name}],
            "Subject": "Password Reset Instructions",
            "TextPart": f"Hello {name},\n\nReset your password here: {settings.FRONTEND_URL}/reset-password?token={token}",
            "HTMLPart": f"<h3>Hello {name}</h3><p>Reset your password <a href='{settings.FRONTEND_URL}/reset-password?token={token}'>here</a></p>"
        }]
    }
    await _send_email(data)
