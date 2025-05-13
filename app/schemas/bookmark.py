from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

class BookmarkBase(BaseModel):
    post_id: UUID

class BookmarkCreate(BookmarkBase):
    pass

class BookmarkRead(BookmarkBase):
    id: UUID
    created_at: datetime
    user_id: UUID
    
    class Config:
        orm_mode = True
