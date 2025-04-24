"""
Complete Post model with all requirements and enum integrations.
References: 
- Posting & Feed
- Admin Panel
"""

from typing import Optional, Dict, List, TYPE_CHECKING
import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import JSON
from sqlalchemy.orm import Mapped
from sqlmodel import SQLModel, Field, Relationship
from pydantic import validator

# Import enums
from app.schemas.enums import Industry, PostType, PostVisibility

if TYPE_CHECKING:
    from app.models.user import User

class PostStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    UNDER_REVIEW = "under_review"
    REJECTED = "rejected"
    ARCHIVED = "archived"

class PostEngagement(SQLModel):
    view_count: int = 0
    share_count: int = 0
    bookmark_count: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "view_count": self.view_count,
            "share_count": self.share_count,
            "bookmark_count": self.bookmark_count
        }

    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> "PostEngagement":
        return cls(**data)

class Post(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    title: str = Field(..., min_length=5, max_length=100)
    content: str = Field(..., min_length=10, max_length=5000)
    post_type: PostType
    industry: Optional[Industry] = Field(default=None, index=True)

    status: PostStatus = Field(default=PostStatus.PUBLISHED)
    visibility: PostVisibility = Field(default=PostVisibility.PUBLIC)
    is_promoted: bool = Field(default=False)

    tags: List[str] = Field(default_factory=list, sa_type=JSON)
    engagement: Dict[str, int] = Field(
        default_factory=lambda: {"view_count": 0, "share_count": 0, "bookmark_count": 0},
        sa_type=JSON
    )

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow}
    )
    published_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    user_id: str = Field(foreign_key="user.id", nullable=False)
    user: Mapped[Optional["User"]] = Relationship(back_populates="posts")

    @validator('expires_at')
    def validate_expiry(cls, v, values):
        if v and values.get('post_type') == PostType.JOB_OPPORTUNITY:
            if v <= datetime.utcnow():
                raise ValueError("Job post must expire in the future")
        return v

    @property
    def is_active(self) -> bool:
        return (
            self.status == PostStatus.PUBLISHED and
            (self.expires_at is None or self.expires_at > datetime.utcnow())
        )

    @property
    def summary(self) -> str:
        return f"{self.content[:150]}..." if len(self.content) > 150 else self.content

    def increment_views(self):
        self.engagement["view_count"] += 1

class PostCreate(SQLModel):
    title: str
    content: str
    post_type: PostType
    industry: Optional[Industry] = None
    tags: List[str] = []
    expires_at: Optional[datetime] = None

    @validator('tags')
    def validate_tags(cls, v):
        if len(v) > 5:
            raise ValueError("Maximum 5 tags allowed")
        return v

class PostUpdate(SQLModel):
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[PostStatus] = None
    visibility: Optional[PostVisibility] = None
    is_promoted: Optional[bool] = None
    expires_at: Optional[datetime] = None

class PostPublic(PostCreate):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    engagement: Dict[str, int]
    is_active: bool

