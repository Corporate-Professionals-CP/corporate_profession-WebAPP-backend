import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import status
from app.models.user import User
from app.schemas.enums import NotificationType


@pytest.mark.asyncio
async def test_update_profile_preferences():
    """Test updating user profile preferences via the API"""
    # Mock user with existing preferences
    mock_user = MagicMock(spec=User)
    mock_user.id = "user123"
    mock_user.profile_preferences = {
        "email_notifications": {
            "email_notifications_enabled": True,
            "email_new_follower": True,
            "email_post_comment": True,
            "email_post_reaction": False
        }
    }
    
    # New preferences to update
    updated_preferences = {
        "email_notifications": {
            "email_notifications_enabled": True,
            "email_new_follower": False,  # Changed
            "email_post_comment": True,
            "email_post_reaction": True,   # Changed
            "email_connection_request": False  # Added new preference
        }
    }
    
    # Update data with new preferences
    update_data = {
        "profile_preferences": updated_preferences
    }
    
    # Mock database session
    mock_db = AsyncMock()
    
    # Mock the get_user_by_id and update_user functions
    with patch("app.api.profiles.get_user_by_id", new=AsyncMock(return_value=mock_user)) as mock_get_user, \
         patch("app.api.profiles.update_user", new=AsyncMock()) as mock_update_user:
        
        # Configure mock_update_user to return updated user
        updated_user = MagicMock(spec=User)
        updated_user.id = "user123"
        updated_user.profile_preferences = updated_preferences
        mock_update_user.return_value = updated_user
        
        # Mock the API client
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        # Mock the authentication dependency
        async def override_get_current_active_user():
            return mock_user
        
        app.dependency_overrides = {}
        
        # Make the API request
        response = await client.put(
            f"/api/profiles/{mock_user.id}",
            json=update_data
        )
        
        # Verify the response
        assert response.status_code == status.HTTP_200_OK
        
        # Verify the user was updated with new preferences
        mock_update_user.assert_called_once()
        assert mock_update_user.call_args[0][1] == mock_user.id
        assert mock_update_user.call_args[0][2] == update_data
        
        # Verify the returned user has the updated preferences
        result = response.json()
        assert result["profile_preferences"] == updated_preferences


@pytest.mark.asyncio
async def test_notification_respects_updated_preferences():
    """Test that notifications respect updated user preferences"""
    # Mock user with updated preferences
    mock_user = MagicMock(spec=User)
    mock_user.id = "user123"
    mock_user.email = "test@example.com"
    mock_user.full_name = "Test User"
    mock_user.profile_preferences = {
        "email_notifications": {
            "email_notifications_enabled": True,
            "email_new_follower": False,  # Disabled for this type
            "email_post_comment": True
        }
    }
    
    # Create notification data for a new follower
    notification_data = {
        "recipient_id": "user123",
        "type": NotificationType.NEW_FOLLOWER,
        "message": "Someone started following you"
    }
    
    # Mock database session
    mock_db = AsyncMock()
    
    # Patch the necessary functions
    with patch("app.crud.notification.get_user", new=AsyncMock(return_value=mock_user)) as mock_get_user, \
         patch("app.crud.notification.should_send_email_notification") as mock_should_send, \
         patch("app.crud.notification.send_notification_email", new=AsyncMock()) as mock_send_email, \
         patch("app.crud.notification.manager.send_personal_notification", new=AsyncMock()), \
         patch("app.crud.notification.get_unread_notification_count", new=AsyncMock(return_value=1)):
        
        # Configure should_send_email_notification to use the real function
        from app.core.email import should_send_email_notification
        mock_should_send.side_effect = should_send_email_notification
        
        # Import and call create_notification
        from app.crud.notification import create_notification
        await create_notification(mock_db, notification_data)
        
        # Verify email notification was not sent (since preference is False)
        assert not mock_send_email.called
        
        # Now test with a different notification type that should send email
        notification_data["type"] = NotificationType.POST_COMMENT
        await create_notification(mock_db, notification_data)
        
        # Verify email notification was sent for this type
        assert mock_send_email.called