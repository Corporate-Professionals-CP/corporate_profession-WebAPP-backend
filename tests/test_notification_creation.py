import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
from app.crud.notification import create_notification
from app.models.notification import Notification
from app.schemas.enums import NotificationType
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_create_notification_with_email(async_test_session: AsyncSession):
    """Test that create_notification sends email when user preferences allow it"""
    # Use the async_test_session fixture instead of creating a mock
    
    # Mock user with email notifications enabled
    mock_user = MagicMock()
    mock_user.email = "test@example.com"
    mock_user.full_name = "Test User"
    mock_user.profile_preferences = {
        "email_notifications": {
            "email_notifications_enabled": True,
            "email_new_follower": True
        }
    }
    
    # Mock actor user
    mock_actor = MagicMock()
    mock_actor.full_name = "Actor User"
    
    # Create notification data
    notification_data = Notification(
        recipient_id="user123",
        actor_id="actor456",
        type=NotificationType.NEW_FOLLOWER,
        message="Actor User started following you",
        created_at=datetime.utcnow(),
        is_read=False
    )
    
    # Patch the necessary functions
    with patch("app.crud.notification.get_user", new=AsyncMock()) as mock_get_user, \
         patch("app.crud.notification.should_send_email_notification", return_value=True) as mock_should_send, \
         patch("app.crud.notification.send_notification_email", new=AsyncMock()) as mock_send_email, \
         patch("app.crud.notification.manager.send_personal_notification", new=AsyncMock()) as mock_send_ws, \
         patch("app.crud.notification.get_unread_notification_count", new=AsyncMock(return_value=5)) as mock_count:
        
        # Configure mock_get_user to return our mock users
        async def mock_get_user_side_effect(db, user_id):
            return mock_user if user_id == "user123" else mock_actor
        
        mock_get_user.side_effect = mock_get_user_side_effect
        
        # Call the function
        result = await create_notification(async_test_session, notification_data)
        
        # Verify the notification was created
        assert result is not None
        
        # Verify WebSocket notification was sent
        assert mock_send_ws.called
        
        # Verify email notification checks and sending
        assert mock_get_user.call_count == 2  # Once for recipient, once for actor
        assert mock_should_send.called
        assert mock_send_email.called
        
        # Verify the email was sent with correct parameters
        mock_send_email.assert_called_once_with(
            recipient_email=mock_user.email,
            recipient_name=mock_user.full_name,
            notification_type=NotificationType.NEW_FOLLOWER,
            actor_name=mock_actor.full_name,
            message="Actor User started following you",
            post_content=None
        )


@pytest.mark.asyncio
async def test_create_notification_without_email(async_test_session: AsyncSession):
    """Test that create_notification doesn't send email when user preferences disallow it"""
    # Use the async_test_session fixture instead of creating a mock
    
    # Mock user with email notifications disabled
    mock_user = MagicMock()
    mock_user.email = "test@example.com"
    mock_user.full_name = "Test User"
    mock_user.profile_preferences = {
        "email_notifications": {
            "email_notifications_enabled": True,
            "email_new_follower": False  # Specifically disabled for this type
        }
    }
    
    # Create notification data
    notification_data = Notification(
        recipient_id="user123",
        type=NotificationType.NEW_FOLLOWER,
        message="Someone started following you",
        created_at=datetime.utcnow(),
        is_read=False
    )
    
    # Patch the necessary functions
    with patch("app.crud.notification.get_user", new=AsyncMock(return_value=mock_user)) as mock_get_user, \
         patch("app.crud.notification.should_send_email_notification", return_value=False) as mock_should_send, \
         patch("app.crud.notification.send_notification_email", new=AsyncMock()) as mock_send_email, \
         patch("app.crud.notification.manager.send_personal_notification", new=AsyncMock()) as mock_send_ws, \
         patch("app.crud.notification.get_unread_notification_count", new=AsyncMock(return_value=5)) as mock_count:
        
        # Call the function
        result = await create_notification(async_test_session, notification_data)
        
        # Verify the notification was created
        assert result is not None
        
        # Verify WebSocket notification was sent
        assert mock_send_ws.called
        
        # Verify email notification was checked but not sent
        assert mock_get_user.called
        assert mock_should_send.called
        assert not mock_send_email.called  # Email should not be sent