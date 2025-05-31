import uuid
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING, List
from sqlalchemy.orm import Mapped, relationship
from sqlalchemy import Column, ARRAY, String

if TYPE_CHECKING:
    from .post import Post
    from .user import User

class PostComment(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    content: str = Field(..., max_length=1000)
    post_id: str = Field(foreign_key="post.id")
    user_id: str = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


    media_url: Optional[str] = Field(default=None)
    media_urls: Optional[List[str]] = Field(default_factory=list, sa_column=Column(ARRAY(String), nullable=True))
    media_type: Optional[str] = Field(default=None)

    post: Mapped["Post"] = Relationship(back_populates="comments")
    user: Mapped["User"] = Relationship()
