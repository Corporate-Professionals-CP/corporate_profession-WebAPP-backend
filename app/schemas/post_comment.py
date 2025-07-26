from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, field_serializer, computed_field
from .user import MinimalUserRead

class PostCommentCreate(BaseModel):
    post_id: str
    content: str
    media_urls: Optional[List[str]] = None

class PostCommentUpdate(BaseModel):
    post_id: str
    content: str
    media_urls: Optional[List[str]] = None

class PostCommentRead(BaseModel):
    content: str
    user_id: str
    post_id: str
    media_urls: Optional[List[str]] = None
    user: Optional[MinimalUserRead] = None
    created_at: datetime

    @field_serializer('media_urls')
    def serialize_media_urls(self, _value, _info):
        if hasattr(self, 'media_url') and self.media_url:
            return self.media_url.split(',')
        return []

    class Config:
        from_attributes = True

