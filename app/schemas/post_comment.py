from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, field_serializer, computed_field
from .user import MinimalUserRead

class PostCommentBase(BaseModel):
    content: str
    user_id: str
    post_id: str
    media_urls: Optional[List[str]] = None

class PostCommentCreate(BaseModel):
    post_id: str
    content: str
    media_urls: Optional[List[str]] = None

class PostCommentUpdate(BaseModel):
    content: str
    media_urls: Optional[List[str]] = None

class PostCommentRead(PostCommentBase):
    id: str
    created_at: datetime
    updated_at: datetime
    user: MinimalUserRead

    class Config:
        from_attributes = True

