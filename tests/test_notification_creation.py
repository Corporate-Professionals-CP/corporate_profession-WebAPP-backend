import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.crud.notification import create_notification
from app.models.notification import Notification


@pytest.mark.asyncio
async def test_create_notification_with_email(db_session):
    """Test creating a notification with email enabled"""
    
    # Mock users
    mock_user = MagicMock()
    mock_user.email = "user@example.com"
    mock_user.full_name = "Test User"
    mock_user.profile_preferences = {"email_notifications": True}
    
    mock_actor = MagicMock()
    mock_actor.email = "actor@example.com"
    mock_actor.full_name = "Actor User"
    
    # Create notification data
    notification_data = {
        "recipient_id": "user123",
        "actor_id": "actor456",
        "type": "connection_request",
        "title": "New Connection Request",
        "message": "You have a new connection request",
        "data": {"connection_id": "conn123"}
    }
    
    with patch('app.crud.notification.get_user') as mock_get_user, \
         patch('app.crud.notification.send_websocket_notification') as mock_ws, \
         patch('app.crud.notification.send_email_notification') as mock_email:
        
        # Configure mocks
        mock_get_user.side_effect = [mock_user, mock_actor]
        mock_ws.return_value = AsyncMock()
        mock_email.return_value = AsyncMock()
        
        # Call the function
        result = await create_notification(db_session, notification_data)
        
        # Assertions
        assert result is not None
        assert result.recipient_id == "user123"
        assert result.actor_id == "actor456"
        assert result.type == "connection_request"
        assert result.title == "New Connection Request"
        assert result.message == "You have a new connection request"
        
        # Verify WebSocket notification was sent
        mock_ws.assert_called_once()
        
        # Verify email notification was sent
        mock_email.assert_called_once_with(
            mock_user.email,
            "New Connection Request",
            "You have a new connection request",
            "connection_request",
            mock_actor
        )


@pytest.mark.asyncio
async def test_create_notification_without_email(db_session):
    """Test creating a notification without email (user preference disabled)"""
    
    # Mock users
    mock_user = MagicMock()
    mock_user.email = "user@example.com"
    mock_user.full_name = "Test User"
    mock_user.profile_preferences = {"email_notifications": False}
    
    mock_actor = MagicMock()
    mock_actor.email = "actor@example.com"
    mock_actor.full_name = "Actor User"
    
    # Create notification data
    notification_data = {
        "recipient_id": "user123",
        "actor_id": "actor456",
        "type": "post_like",
        "title": "Post Liked",
        "message": "Someone liked your post",
        "data": {"post_id": "post123"}
    }
    
    with patch('app.crud.notification.get_user') as mock_get_user, \
         patch('app.crud.notification.send_websocket_notification') as mock_ws, \
         patch('app.crud.notification.send_email_notification') as mock_email:
        
        # Configure mocks
        mock_get_user.side_effect = [mock_user, mock_actor]
        mock_ws.return_value = AsyncMock()
        mock_email.return_value = AsyncMock()
        
        # Call the function
        result = await create_notification(db_session, notification_data)
        
        # Assertions
        assert result is not None
        assert result.recipient_id == "user123"
        assert result.actor_id == "actor456"
        assert result.type == "post_like"
        
        # Verify WebSocket notification was sent
        mock_ws.assert_called_once()
        
        # Verify email notification was NOT sent (user preference disabled)
        mock_email.assert_not_called()