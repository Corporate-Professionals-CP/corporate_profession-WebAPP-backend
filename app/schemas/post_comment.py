from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from .user import MinimalUserRead

class PostCommentCreate(BaseModel):
    post_id: str
    content: str

class PostCommentUpdate(BaseModel):
    post_id: str
    content: str

class PostCommentRead(BaseModel):
    content: str
    user_id: str
    post_id: str
    user: MinimalUserRead
    created_at: datetime

    class Config:
        orm_mode = True

