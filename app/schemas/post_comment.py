from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class PostCommentCreate(BaseModel):
    post_id: str
    content: str

class PostCommentUpdate(BaseModel):
    post_id: str
    content: str

class PostCommentRead(BaseModel):
    id: str
    content: str
    user_id: str
    post_id: str
    created_at: datetime

    class Config:
        orm_mode = True

