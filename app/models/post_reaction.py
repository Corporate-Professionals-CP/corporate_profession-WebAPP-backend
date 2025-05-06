from enum import Enum
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from sqlalchemy.orm import Mapped, relationship

if TYPE_CHECKING:
    from .post import Post
    from .user import User

class ReactionType(str, Enum):
    LIKE = "like"
    LOVE = "love"
    INSIGHTFUL = "insightful"
    FUNNY = "funny"
    CONGRATULATIONS = "congratulations"

class PostReaction(SQLModel, table=True):
    user_id: str = Field(foreign_key="user.id", primary_key=True)
    post_id: str = Field(foreign_key="post.id", primary_key=True)
    type: ReactionType = Field(default=ReactionType.LIKE)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    post: Mapped["Post"] = Relationship(back_populates="reactions")
    user: Mapped["User"] = Relationship()

