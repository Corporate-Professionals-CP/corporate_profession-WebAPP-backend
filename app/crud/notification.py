import logging
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.notification import Notification
from sqlalchemy import select, func
from app.core.ws_manager import manager
from sqlalchemy.orm import selectinload
from app.crud.user import generate_avatar_fallback
from typing import Union, Dict, Any

logger = logging.getLogger(__name__)

async def create_notification(
    db: AsyncSession, 
    notification_data: Union[Dict[str, Any], Notification]
) -> Notification:
    """
    Creates a notification and sends it via WebSocket.
    Handles both dictionary input and Notification object input.
    
    Args:
        db: Async database session
        notification_data: Either a dictionary of notification attributes 
                         or a Notification object
        
    Returns:
        The created Notification object
    
    Raises:
        ValueError: If notification_data is invalid
        TypeError: If notification_data has wrong type
    """
    try:
        # Handle both dict and Notification object inputs
        if isinstance(notification_data, Notification):
            notification = notification_data
            db.add(notification)
        elif isinstance(notification_data, dict):
            # Validate required fields
            required_fields = ['recipient_id', 'type', 'message']
            if not all(field in notification_data for field in required_fields):
                missing = [f for f in required_fields if f not in notification_data]
                raise ValueError(f"Missing required notification fields: {missing}")
            
            # Set defaults
            notification_data.setdefault('is_read', False)
            notification_data.setdefault('created_at', datetime.utcnow())
            
            notification = Notification(**notification_data)
            db.add(notification)
        else:
            raise TypeError("notification_data must be either a dict or Notification object")

        await db.commit()
        await db.refresh(notification)

        # Prepare WebSocket payload
        ws_payload = {
            "id": str(notification.id),
            "type": notification.type.value,
            "message": notification.message,
            "is_read": notification.is_read,
            "created_at": notification.created_at.isoformat(),
            "actor_id": notification.actor_id,
            "reference_id": notification.reference_id
        }

        # Send via WebSocket (fail silently if error occurs)
        try:
            await manager.send_personal_notification(
                notification.recipient_id,
                ws_payload
            )
        except Exception as ws_error:
            logger.error(f"Failed to send WebSocket notification: {ws_error}")
            # Continue even if WebSocket fails

        # Get updated unread count
        new_count = await get_unread_notification_count(db, notification.recipient_id)

        # Send WebSocket update
        await manager.send_personal_notification(
            notification.recipient_id,
            {
                "type": "unread_count_update",
                "count": new_count,
                "change": "+1"  # Indicates increment
            }
        )

        return notification

    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create notification: {e}")
        raise  # Re-raise the exception for the caller to handle

async def get_user_notifications(db: AsyncSession, user_id: str):
    """Get all notifications for user with relationships loaded"""
    result = await db.execute(
        select(Notification)
        .where(Notification.recipient_id == user_id)
        .options(
            selectinload(Notification.actor),
            selectinload(Notification.post),
            selectinload(Notification.comment)
        )
        .order_by(Notification.created_at.desc())
    )
    notifications = result.scalars().all()
    
    notification_list = []
    for n in notifications:
        actor_data = None
        if n.actor:
            initials, color = generate_avatar_fallback(n.actor)
            actor_data = {
                "id": n.actor.id,
                "full_name": n.actor.full_name,
                "avatar": {
                    "initials": initials,
                    "color": color
                }
            }
        
        post_data = None
        if n.post:
            post_data = {
                "id": n.post.id,
                "content": n.post.content
            }
        
        notification_list.append({
            "id": str(n.id),
            "type": n.type.value,
            "message": n.message,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat(),
            "actor": actor_data,
            "post": post_data,
            "reference_id": n.reference_id
        })
    
    return notification_list

async def mark_as_read(db: AsyncSession, notif_id: str, user_id: str) -> bool:
    """Mark notification as read and update unread count"""
    result = await db.execute(
        select(Notification)
        .where(
            Notification.id == notif_id,
            Notification.recipient_id == user_id,
            Notification.is_read == False  # Only if currently unread
        )
    )
    notif = result.scalar_one_or_none()
    
    if notif:
        notif.is_read = True
        await db.commit()
        
        # Get updated unread count
        new_count = await get_unread_notification_count(db, user_id)
        
        # Send WebSocket update
        await manager.send_personal_notification(
            user_id,
            {
                "type": "unread_count_update",
                "count": new_count,
                "change": "-1"  # Indicates decrement
            }
        )
        return True
    return False

async def get_unread_notification_count(db: AsyncSession, user_id: str) -> int:
    result = await db.execute(
        select(func.count(Notification.id))
        .where(
            Notification.recipient_id == user_id,
            Notification.is_read == False
        )
    )
    return result.scalar()
