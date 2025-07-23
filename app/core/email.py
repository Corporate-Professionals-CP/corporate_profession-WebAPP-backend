import logging
import asyncio
import resend
import random
import string
from fastapi import HTTPException, status
from app.core.config import settings
from app.schemas.enums import NotificationType
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
    
    text = f"Hello {name},\n\nYour verification code is: {otp}\n\nEnter this code to verify your email."
    html = f"""
        <h3>Hello {name},</h3>
        <p>Your verification code is: <strong>{otp}</strong></p>
        <p>Enter this code to verify your email.</p>
    """
    
    # We'll return the OTP to store it in the user record
    return otp, await _send_email_resend(email, name, subject, text, html)

async def send_password_reset_email(email: str, name: str) -> str:
    """Send password reset OTP email and return the generated OTP"""
    subject = "Password Reset OTP"
    otp = await generate_otp()

    text = f"Hello {name},\n\nYour password reset OTP is: {otp}\n\nEnter this code to reset your password."
    html = f"""
        <h3>Hello {name},</h3>
        <p>Your password reset OTP is: <strong>{otp}</strong></p>
        <p>Enter this code to reset your password.</p>
    """

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


# Notification email templates
NOTIFICATION_TEMPLATES = {
    NotificationType.NEW_FOLLOWER: {
        "subject": "New Follower on Corporate Professionals",
        "text": "Hello {recipient_name},\n\n{actor_name} started following you on Corporate Professionals.\n\nView your profile: {profile_url}\n\nBest regards,\nCorporate Professionals Team",
        "html": """
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2563eb;">New Follower!</h2>
            <p>Hello <strong>{recipient_name}</strong>,</p>
            <p><strong>{actor_name}</strong> started following you on Corporate Professionals.</p>
            <div style="margin: 20px 0;">
                <a href="{profile_url}" style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">View Your Profile</a>
            </div>
            <p>Best regards,<br>Corporate Professionals Team</p>
        </div>
        """
    },
    NotificationType.POST_COMMENT: {
        "subject": "New Comment on Your Post",
        "text": "Hello {recipient_name},\n\n{actor_name} commented on your post: \"{post_content}\"\n\nComment: {message}\n\nView post: {post_url}\n\nBest regards,\nCorporate Professionals Team",
        "html": """
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2563eb;">New Comment on Your Post</h2>
            <p>Hello <strong>{recipient_name}</strong>,</p>
            <p><strong>{actor_name}</strong> commented on your post:</p>
            <div style="background-color: #f3f4f6; padding: 15px; border-radius: 6px; margin: 15px 0;">
                <p style="margin: 0; font-style: italic;">\"{post_content}\"</p>
            </div>
            <p><strong>Comment:</strong> {message}</p>
            <div style="margin: 20px 0;">
                <a href="{post_url}" style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">View Post</a>
            </div>
            <p>Best regards,<br>Corporate Professionals Team</p>
        </div>
        """
    },
    NotificationType.POST_REACTION: {
        "subject": "Someone Reacted to Your Post",
        "text": "Hello {recipient_name},\n\n{actor_name} reacted to your post: \"{post_content}\"\n\nView post: {post_url}\n\nBest regards,\nCorporate Professionals Team",
        "html": """
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2563eb;">New Reaction on Your Post</h2>
            <p>Hello <strong>{recipient_name}</strong>,</p>
            <p><strong>{actor_name}</strong> reacted to your post:</p>
            <div style="background-color: #f3f4f6; padding: 15px; border-radius: 6px; margin: 15px 0;">
                <p style="margin: 0; font-style: italic;">\"{post_content}\"</p>
            </div>
            <div style="margin: 20px 0;">
                <a href="{post_url}" style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">View Post</a>
            </div>
            <p>Best regards,<br>Corporate Professionals Team</p>
        </div>
        """
    },
    NotificationType.CONNECTION_REQUEST: {
        "subject": "New Connection Request",
        "text": "Hello {recipient_name},\n\n{actor_name} sent you a connection request on Corporate Professionals.\n\nView request: {connections_url}\n\nBest regards,\nCorporate Professionals Team",
        "html": """
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2563eb;">New Connection Request</h2>
            <p>Hello <strong>{recipient_name}</strong>,</p>
            <p><strong>{actor_name}</strong> sent you a connection request on Corporate Professionals.</p>
            <div style="margin: 20px 0;">
                <a href="{connections_url}" style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">View Request</a>
            </div>
            <p>Best regards,<br>Corporate Professionals Team</p>
        </div>
        """
    },
    NotificationType.CONNECTION_ACCEPTED: {
        "subject": "Connection Request Accepted",
        "text": "Hello {recipient_name},\n\n{actor_name} accepted your connection request on Corporate Professionals.\n\nView connections: {connections_url}\n\nBest regards,\nCorporate Professionals Team",
        "html": """
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2563eb;">Connection Request Accepted</h2>
            <p>Hello <strong>{recipient_name}</strong>,</p>
            <p><strong>{actor_name}</strong> accepted your connection request on Corporate Professionals.</p>
            <div style="margin: 20px 0;">
                <a href="{connections_url}" style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">View Connections</a>
            </div>
            <p>Best regards,<br>Corporate Professionals Team</p>
        </div>
        """
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
        if notification_type not in NOTIFICATION_TEMPLATES:
            logger.warning(f"No email template found for notification type: {notification_type}")
            return

        template = NOTIFICATION_TEMPLATES[notification_type]
        
        # Prepare template variables
        template_vars = {
            "recipient_name": recipient_name,
            "actor_name": actor_name or "Someone",
            "message": message or "",
            "post_content": (post_content[:100] + "...") if post_content and len(post_content) > 100 else (post_content or ""),
            "profile_url": f"{settings.FRONTEND_URL}/profile",
            "post_url": f"{settings.FRONTEND_URL}/posts",
            "connections_url": f"{settings.FRONTEND_URL}/connections",
            **kwargs
        }
        
        # Format template strings
        subject = template["subject"].format(**template_vars)
        text = template["text"].format(**template_vars)
        html = template["html"].format(**template_vars)
        
        await _send_email_resend(recipient_email, recipient_name, subject, text, html)
        logger.info(f"Notification email sent to {recipient_email} for {notification_type}")
        
    except Exception as e:
        logger.error(f"Failed to send notification email to {recipient_email}: {str(e)}")
        # Don't raise exception to avoid breaking the notification flow
