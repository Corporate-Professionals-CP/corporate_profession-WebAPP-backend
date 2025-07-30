from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel

from app.schemas.enums import NotificationType
from app.schemas.post import PostRead
from app.schemas.user import UserPublic

class AvatarData(BaseModel):
    initials: str
    color: str

class NotificationActor(BaseModel):
    id: str
    full_name: Optional[str] = None
    avatar: AvatarData

class NotificationPost(BaseModel):
    id: str
    content: str


class NotificationRead(BaseModel):
    id: UUID
    type: NotificationType
    message: str
    is_read: bool
    created_at: str

    actor: Optional[NotificationActor] = None
    post: Optional[NotificationPost] = None
    reference_id: Optional[str] = None


    class Config:
        from_attributes = True

class NotificationResponse(BaseModel):
    unread_count: int
    notifications: List[NotificationRead]

    class Config:
        from_attributes = True

class NotificationNavigation(BaseModel):
    """Navigation information for a notification"""
    url: str
    type: str  # 'profile', 'post', 'connections', 'messages', etc.
    target_id: Optional[str] = None  # ID of the target resource

class NotificationReadResponse(BaseModel):
    """Response when reading a notification with navigation info"""
    notification: NotificationRead
    navigation: NotificationNavigation
    
    class Config:
        from_attributes = True
