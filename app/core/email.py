import logging
import asyncio
import resend
import random
import string
from fastapi import HTTPException, status
from app.core.config import settings
from app.schemas.enums import NotificationType
from app.utils.template_loader import template_loader
from typing import Dict, Any, Optional
from datetime import datetime

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
    
    context = {
        "name": name,
        "otp": otp,
        "frontend_url": settings.FRONTEND_URL
    }
    
    html = template_loader.render_template("verification_email", context)
    text = template_loader.get_text_version(html)
    
    # We'll return the OTP to store it in the user record
    return otp, await _send_email_resend(email, name, subject, text, html)

async def send_password_reset_email(email: str, name: str) -> str:
    """Send password reset OTP email and return the generated OTP"""
    subject = "Password Reset OTP"
    otp = await generate_otp()

    context = {
        "name": name,
        "otp": otp,
        "frontend_url": settings.FRONTEND_URL
    }
    
    html = template_loader.render_template("password_reset", context)
    text = template_loader.get_text_version(html)

    await _send_email_resend(email, name, subject, text, html)
    return otp


# This function is replaced by the more comprehensive version below


def should_send_email_notification(notification_type: NotificationType, user_preferences: Dict[str, Any]) -> bool:
    """Check if email notification should be sent based on user preferences"""
    
    # Default email notification settings
    default_email_settings = {
        "email_notifications_enabled": True,
        "email_new_follower": True,
        "email_post_comment": True,
        "email_post_reaction": False,  # Usually too frequent
        "email_connection_request": True,
        "email_connection_accepted": True,
        "email_new_message": True,
        "email_post_tag": True,
        "email_bookmark": False,
        "email_job_application": True,
        "email_post_repost": False
    }
    
    # Get user's email preferences (stored in profile_preferences)
    email_prefs = user_preferences.get("email_notifications", default_email_settings)
    
    # Check if email notifications are globally enabled
    if not email_prefs.get("email_notifications_enabled", True):
        return False
    
    # Check specific notification type preference
    notification_key_map = {
        NotificationType.NEW_FOLLOWER: "email_new_follower",
        NotificationType.POST_COMMENT: "email_post_comment",
        NotificationType.POST_REACTION: "email_post_reaction",
        NotificationType.CONNECTION_REQUEST: "email_connection_request",
        NotificationType.CONNECTION_ACCEPTED: "email_connection_accepted",
        NotificationType.NEW_MESSAGE: "email_new_message",
        NotificationType.POST_TAG: "email_post_tag",
        NotificationType.BOOKMARK: "email_bookmark",
        NotificationType.JOB_APPLICATION: "email_job_application",
        NotificationType.POST_REPOST: "email_post_repost"
    }
    
    pref_key = notification_key_map.get(notification_type)
    if pref_key:
        return email_prefs.get(pref_key, default_email_settings.get(pref_key, False))
    
    return False


# Email template mapping for notifications
NOTIFICATION_TEMPLATE_MAP = {
    NotificationType.NEW_FOLLOWER: {
        "template": "new_follower",
        "subject": "New Follower on Corporate Professionals"
    },
    NotificationType.POST_COMMENT: {
        "template": "post_comment",
        "subject": "New Comment on Your Post"
    },
    NotificationType.POST_REACTION: {
        "template": "post_reaction",
        "subject": "Someone Reacted to Your Post"
    },
    NotificationType.CONNECTION_REQUEST: {
        "template": "connection_request",
        "subject": "New Connection Request"
    },
    NotificationType.CONNECTION_ACCEPTED: {
        "template": "connection_accepted",
        "subject": "Connection Request Accepted"
    }
}


async def send_notification_email(
    recipient_email: str,
    recipient_name: str,
    notification_type: NotificationType,
    actor_name: str = None,
    message: str = None,
    post_content: str = None,
    **kwargs
) -> None:
    """Send notification email based on notification type"""
    try:
        if notification_type not in NOTIFICATION_TEMPLATE_MAP:
            logger.warning(f"No email template found for notification type: {notification_type}")
            return

        template_config = NOTIFICATION_TEMPLATE_MAP[notification_type]
        template_name = template_config["template"]
        subject = template_config["subject"]
        
        # Prepare template context
        context = {
            "recipient_name": recipient_name,
            "actor_name": actor_name or "Someone",
            "message": message or "",
            "post_content": (post_content[:100] + "...") if post_content and len(post_content) > 100 else (post_content or ""),
            "profile_url": f"{settings.FRONTEND_URL}/profile",
            "post_url": f"{settings.FRONTEND_URL}/posts",
            "connections_url": f"{settings.FRONTEND_URL}/connections",
            "frontend_url": settings.FRONTEND_URL,
            **kwargs
        }
        
        # Render template
        html = template_loader.render_template(template_name, context)
        text = template_loader.get_text_version(html)
        
        await _send_email_resend(recipient_email, recipient_name, subject, text, html)
        logger.info(f"Notification email sent to {recipient_email} for {notification_type}")
        
    except Exception as e:
        logger.error(f"Failed to send notification email to {recipient_email}: {str(e)}")
        # Don't raise exception to avoid breaking the notification flow
