from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel

from app.schemas.enums import NotificationType
from app.schemas.post import PostRead
from app.schemas.user import UserPublic

class NotificationRead(BaseModel):
    id: UUID
    type: NotificationType
    message: str
    is_read: bool
    created_at: datetime

    actor: Optional[UserPublic]
    post: Optional[PostRead]

    class Config:
        from_attributes = True

class NotificationResponse(BaseModel):
    unread_count: int
    notifications: List[NotificationRead]

    class Config:
        from_attributes = True
