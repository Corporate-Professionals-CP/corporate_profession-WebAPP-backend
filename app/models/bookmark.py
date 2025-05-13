from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from uuid import uuid4
from datetime import datetime
from sqlalchemy.orm import Mapped

class Bookmark(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="user.id")
    post_id: str = Field(foreign_key="post.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    user: Mapped["User"] = Relationship(back_populates="bookmarks")
    post: Mapped["Post"] = Relationship(back_populates="bookmarks")
