"""
Post database model with improved type safety and relationships.
PRD Reference: Section 2.5 (Posting & Feed)
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import or_
from app.models.user import User
from app.schemas.enums import Industry

class PostType(str, Enum):
    """Defines allowed post types"""
    JOB_OPPORTUNITY = "job_opportunity"
    ANNOUNCEMENT = "announcement"
    PROFESSIONAL_UPDATE = "professional_update"

def generate_uuid() -> str:
    """Generate UUID string for primary keys"""
    return str(uuid.uuid4())

class Post(SQLModel, table=True):
    """
    Professional content post model.
    PRD Requirements:
    - Any user can create posts
    - Posts can be tagged by industry
    - Feed shows relevant posts
    """
    id: str = Field(default_factory=generate_uuid, primary_key=True, index=True)
    title: str = Field(..., min_length=5, max_length=100)
    content: str = Field(..., min_length=10, max_length=2000)
    post_type: PostType
    industry: Optional[Industry] = Field(default=None, index=True)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow}
    )

    # Relationships
    user_id: str = Field(foreign_key="user.id")
    user: User = Relationship(back_populates="posts")

    @property
    def summary(self) -> str:
        """Generate a shortened preview of the post content"""
        return f"{self.content[:100]}..." if len(self.content) > 100 else self.content