import uuid
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from sqlalchemy.orm import Mapped, relationship

if TYPE_CHECKING:
    from .post import Post
    from .user import User

class PostComment(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    content: str = Field(..., max_length=1000)
    post_id: str = Field(foreign_key="post.id")
    user_id: str = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    post: Mapped["Post"] = Relationship(back_populates="comments")
    user: Mapped["User"] = Relationship()
