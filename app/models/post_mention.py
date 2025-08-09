from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from uuid import uuid4
from datetime import datetime
from sqlalchemy.orm import Mapped, relationship
from sqlalchemy import Index

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.post import Post

class PostMention(SQLModel, table=True):
    """Model for tracking user mentions in posts"""
    __tablename__ = "post_mention"
    __table_args__ = (
        Index("ix_post_mention_mentioned_user_id", "mentioned_user_id"),
        Index("ix_post_mention_post_id", "post_id"),
        Index("ix_post_mention_mentioned_by_user_id", "mentioned_by_user_id"),
        Index("ix_post_mention_created_at", "created_at"),
        Index("ix_post_mention_user_date", "mentioned_user_id", "created_at"),
        Index("ix_post_mention_post_date", "post_id", "created_at"),
    )
    
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    post_id: str = Field(foreign_key="post.id", nullable=False)
    mentioned_user_id: str = Field(foreign_key="user.id", nullable=False)
    mentioned_by_user_id: str = Field(foreign_key="user.id", nullable=False)
    mention_text: str = Field(..., description="The actual mention text (e.g., @john_doe)")
    position_start: int = Field(..., description="Start position of mention in post content")
    position_end: int = Field(..., description="End position of mention in post content")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    post: Mapped["Post"] = Relationship(
        back_populates="mentions",
        sa_relationship_kwargs={"foreign_keys": "[PostMention.post_id]"}
    )
    
    mentioned_user: Mapped["User"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[PostMention.mentioned_user_id]",
            "lazy": "selectin",
            "overlaps": "mentions_received"
        }
    )
    
    mentioned_by: Mapped["User"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[PostMention.mentioned_by_user_id]",
            "lazy": "selectin",
            "overlaps": "mentions_made"
        }
    )