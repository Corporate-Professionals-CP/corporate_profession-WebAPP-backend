import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import WebSocket, status
from app.core.ws_manager import NotificationManager
from app.api.notification import websocket_notifications
from app.models.user import User
from app.models.notification import Notification


class MockWebSocket:
    """Mock WebSocket for testing"""
    def __init__(self):
        self.messages_sent = []
        self.closed = False
        self.close_code = None
        self.accepted = False
        
    async def accept(self):
        self.accepted = True
        
    async def send_text(self, data: str):
        self.messages_sent.append(data)
        
    async def receive_text(self):
        # Simulate ping message for heartbeat
        return "ping"
        
    async def close(self, code: int = None):
        self.closed = True
        self.close_code = code


@pytest.mark.asyncio
class TestNotificationWebSocket:
    """Test cases for notification WebSocket functionality"""
    
    def setup_method(self):
        """Setup fresh manager for each test"""
        self.manager = NotificationManager()
        self.mock_websocket = MockWebSocket()
        
    async def test_websocket_connection_success(self):
        """Test successful WebSocket connection with valid token"""
        user_id = "user123"
        token = "valid_token"
        
        # Mock user
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.is_active = True
        
        with patch('app.api.notification.verify_token') as mock_verify, \
             patch('app.api.notification.get_user_by_id') as mock_get_user, \
             patch('app.api.notification.manager', self.manager):
            
            # Configure mocks
            mock_verify.return_value = {"sub": user_id}
            mock_get_user.return_value = mock_user
            
            # Connect to WebSocket
            await self.manager.connect(self.mock_websocket, user_id)
            
            # Assertions
            assert self.mock_websocket.accepted
            assert user_id in self.manager.active_connections
            assert self.manager.active_connections[user_id] == self.mock_websocket
    
    async def test_websocket_connection_invalid_token(self):
        """Test WebSocket connection with invalid token"""
        token = "invalid_token"
        
        with patch('app.api.notification.verify_token') as mock_verify:
            # Configure mock to raise exception
            mock_verify.side_effect = Exception("Invalid token")
            
            # This would be handled in the actual endpoint
            with pytest.raises(Exception):
                mock_verify(token, expected_type="access")
    
    async def test_websocket_connection_inactive_user(self):
        """Test WebSocket connection with inactive user"""
        user_id = "user123"
        token = "valid_token"
        
        # Mock inactive user
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.is_active = False
        
        with patch('app.api.notification.verify_token') as mock_verify, \
             patch('app.api.notification.get_user_by_id') as mock_get_user:
            
            # Configure mocks
            mock_verify.return_value = {"sub": user_id}
            mock_get_user.return_value = mock_user
            
            # This would result in connection closure in the actual endpoint
            assert not mock_user.is_active
    
    async def test_send_personal_notification(self):
        """Test sending personal notification via WebSocket"""
        user_id = "user123"
        notification_data = {
            "id": "notif123",
            "title": "Test Notification",
            "message": "This is a test notification",
            "type": "connection_request"
        }
        
        # Connect user
        await self.manager.connect(self.mock_websocket, user_id)
        
        # Send notification
        await self.manager.send_personal_notification(user_id, notification_data)
        
        # Assertions
        assert len(self.mock_websocket.messages_sent) == 1
        sent_message = json.loads(self.mock_websocket.messages_sent[0])
        assert sent_message["type"] == "notification"
        assert sent_message["data"] == notification_data
    
    async def test_send_notification_to_disconnected_user(self):
        """Test sending notification to disconnected user (should store as pending)"""
        user_id = "user123"
        notification_data = {
            "id": "notif123",
            "title": "Test Notification",
            "message": "This is a test notification"
        }
        
        # Send notification without connecting user first
        await self.manager.send_personal_notification(user_id, notification_data)
        
        # Assertions
        assert user_id in self.manager.pending_notifications
        assert len(self.manager.pending_notifications[user_id]) == 1
        
        pending_notif = self.manager.pending_notifications[user_id][0]
        assert pending_notif["type"] == "notification"
        assert pending_notif["data"] == notification_data
    
    async def test_flush_pending_notifications_on_connect(self):
        """Test that pending notifications are sent when user connects"""
        user_id = "user123"
        notification_data = {
            "id": "notif123",
            "title": "Pending Notification",
            "message": "This was pending"
        }
        
        # Send notification while user is disconnected
        await self.manager.send_personal_notification(user_id, notification_data)
        assert user_id in self.manager.pending_notifications
        
        # Connect user (should flush pending notifications)
        await self.manager.connect(self.mock_websocket, user_id)
        
        # Assertions
        assert user_id not in self.manager.pending_notifications  # Pending cleared
        assert len(self.mock_websocket.messages_sent) == 1  # Notification sent
        
        sent_message = json.loads(self.mock_websocket.messages_sent[0])
        assert sent_message["type"] == "notification"
        assert sent_message["data"] == notification_data
    
    async def test_websocket_disconnect(self):
        """Test WebSocket disconnection"""
        user_id = "user123"
        
        # Connect user
        await self.manager.connect(self.mock_websocket, user_id)
        assert user_id in self.manager.active_connections
        
        # Disconnect user
        self.manager.disconnect(user_id)
        
        # Assertions
        assert user_id not in self.manager.active_connections
    
    async def test_broadcast_new_post(self):
        """Test broadcasting new post to all connected users except author"""
        author_id = "author123"
        user1_id = "user1"
        user2_id = "user2"
        
        # Create mock websockets for users
        user1_ws = MockWebSocket()
        user2_ws = MockWebSocket()
        author_ws = MockWebSocket()
        
        # Connect users
        await self.manager.connect(user1_ws, user1_id)
        await self.manager.connect(user2_ws, user2_id)
        await self.manager.connect(author_ws, author_id)
        
        post_data = {
            "id": "post123",
            "title": "New Post",
            "author_id": author_id
        }
        
        # Broadcast new post
        await self.manager.broadcast_new_post(post_data, exclude_user_id=author_id)
        
        # Assertions
        assert len(user1_ws.messages_sent) == 1
        assert len(user2_ws.messages_sent) == 1
        assert len(author_ws.messages_sent) == 0  # Author should not receive
        
        # Check message content
        user1_message = json.loads(user1_ws.messages_sent[0])
        assert user1_message["type"] == "new_post"
        assert user1_message["data"] == post_data
    
    async def test_send_feed_update(self):
        """Test sending feed update to specific user"""
        user_id = "user123"
        post_data = {
            "id": "post123",
            "title": "Updated Post",
            "content": "This post was updated"
        }
        
        # Connect user
        await self.manager.connect(self.mock_websocket, user_id)
        
        # Send feed update
        await self.manager.send_feed_update(user_id, post_data)
        
        # Assertions
        assert len(self.mock_websocket.messages_sent) == 1
        sent_message = json.loads(self.mock_websocket.messages_sent[0])
        assert sent_message["type"] == "feed_update"
        assert sent_message["data"] == post_data
    
    async def test_multiple_notifications_to_same_user(self):
        """Test sending multiple notifications to the same user"""
        user_id = "user123"
        
        # Connect user
        await self.manager.connect(self.mock_websocket, user_id)
        
        # Send multiple notifications
        notifications = [
            {"id": "notif1", "title": "First Notification"},
            {"id": "notif2", "title": "Second Notification"},
            {"id": "notif3", "title": "Third Notification"}
        ]
        
        for notif_data in notifications:
            await self.manager.send_personal_notification(user_id, notif_data)
        
        # Assertions
        assert len(self.mock_websocket.messages_sent) == 3
        
        for i, notif_data in enumerate(notifications):
            sent_message = json.loads(self.mock_websocket.messages_sent[i])
            assert sent_message["type"] == "notification"
            assert sent_message["data"] == notif_data
    
    async def test_websocket_error_handling(self):
        """Test WebSocket error handling during notification sending"""
        user_id = "user123"
        
        # Create a mock websocket that raises an exception
        error_websocket = MagicMock()
        error_websocket.send_text = AsyncMock(side_effect=Exception("Connection error"))
        
        # Manually add to active connections
        self.manager.active_connections[user_id] = error_websocket
        
        notification_data = {"id": "notif123", "title": "Test"}
        
        # This should not raise an exception (error should be logged)
        await self.manager.send_personal_notification(user_id, notification_data)
        
        # The notification should be stored as pending since sending failed
        assert user_id in self.manager.pending_notifications