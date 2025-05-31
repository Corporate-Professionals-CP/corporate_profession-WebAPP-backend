import json
from typing import Dict, List
from fastapi import WebSocket
import logging
from uuid import UUID

logger = logging.getLogger(__name__)

class NotificationManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.pending_notifications: Dict[str, List[dict]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        await self._flush_pending(user_id)

    async def _flush_pending(self, user_id: str):
        if user_id in self.pending_notifications:
            for notification in self.pending_notifications[user_id]:
                await self._send_notification(user_id, notification)
            del self.pending_notifications[user_id]

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def _send_notification(self, user_id: str, notification: dict):
        try:
            if user_id in self.active_connections:
                await self.active_connections[user_id].send_text(json.dumps(notification))
            else:
                self._store_pending(user_id, notification)
        except Exception as e:
            logger.error(f"Error sending notification to {user_id}: {str(e)}")

    def _store_pending(self, user_id: str, notification: dict):
        if user_id not in self.pending_notifications:
            self.pending_notifications[user_id] = []
        self.pending_notifications[user_id].append(notification)

    async def send_personal_notification(self, user_id: str, notification_data: dict):
        notification = {
            "type": "notification",
            "data": notification_data
        }
        await self._send_notification(user_id, notification)

# Singleton instance
manager = NotificationManager()
