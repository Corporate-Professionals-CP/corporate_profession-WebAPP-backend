"""
User Activity Logging Utility
Tracks user activities for admin analytics
"""

from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user_admin import UserActivityLog
import logging

logger = logging.getLogger(__name__)


async def log_user_activity(
    db: AsyncSession,
    user_id: str,
    activity_type: str,
    description: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Log user activity for admin tracking
    
    Args:
        db: Database session
        user_id: ID of the user performing the activity
        activity_type: Type of activity (login, post_created, connection_made, etc.)
        description: Human readable description
        ip_address: User's IP address
        user_agent: User's browser/app info
        metadata: Additional data as JSON
    """
    try:
        activity = UserActivityLog(
            user_id=user_id,
            activity_type=activity_type,
            activity_description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata or {}
        )
        
        db.add(activity)
        await db.commit()
        
    except Exception as e:
        logger.error(f"Failed to log user activity: {e}")
        await db.rollback()


# Common activity types
class ActivityType:
    LOGIN = "login"
    LOGOUT = "logout"
    POST_CREATED = "post_created"
    POST_DELETED = "post_deleted"
    CONNECTION_SENT = "connection_sent"
    CONNECTION_ACCEPTED = "connection_accepted"
    PROFILE_UPDATED = "profile_updated"
    PASSWORD_CHANGED = "password_changed"
    EMAIL_VERIFIED = "email_verified"
    BOOKMARK_ADDED = "bookmark_added"
    COMMENT_POSTED = "comment_posted"
    REACTION_ADDED = "reaction_added"
