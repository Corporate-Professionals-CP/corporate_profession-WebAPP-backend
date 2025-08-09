"""
Complete Post model with all requirements and enum integrations.
References: 
- Posting & Feed
- Admin Panel
"""

from typing import Optional, Dict, List, TYPE_CHECKING, ClassVar
import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import and_, or_
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Column, Enum as PgEnum, JSON, String, Column, ARRAY
from sqlalchemy.orm import Mapped, relationship
from sqlmodel import SQLModel, Field, Relationship
from pydantic import validator
from app.models.skill import Skill, PostSkill
from app.models.post_comment import PostComment
from app.models.post_reaction import PostReaction
from app.models.follow import UserFollow

from app.schemas.enums import PostType, PostVisibility, ExperienceLevel

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.bookmark import Bookmark
    from app.models.company import Company
    from app.models.post_mention import PostMention

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
    title: Optional[str] = Field(None, nullable=True)
    content: str = Field(..., min_length=10, max_length=5000)
    post_type: PostType = Field(
        sa_column=Column(
            PgEnum(PostType, values_callable=lambda enum_cls: [e.value for e in enum_cls], name="posttype"),
            nullable=False
        )
    )
    job_title: Optional[str] = Field(
        default=None,
        index=True,
        max_length=50
    )
    industry: Optional[str] = Field(default=None, index=True)
    experience_level: Optional[ExperienceLevel] = Field(default=None)

    status: PostStatus = Field(default=PostStatus.PUBLISHED, index=True)
    visibility: PostVisibility = Field(default=PostVisibility.PUBLIC, index=True)
    is_promoted: bool = Field(default=False, index=True)
    is_active: ClassVar[hybrid_property]
    skill_names: ClassVar[list[str]] = []
    deleted: bool = Field(default=False, index=True) # using for the soft delete

    tags: List[str] = Field(default_factory=list, sa_type=JSON)
    engagement: PostEngagement = Field(
        default=PostEngagement().dict(),
        sa_column=Column(JSONB, nullable=False, default=lambda: PostEngagement().dict())
    )
    media_urls: Optional[List[str]] = Field(default_factory=list, sa_column=Column(ARRAY(String), nullable=True))
    media_url: Optional[str] = None
    media_type: Optional[str] = Field(default="image", max_length=50)  # or "video"


    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow},
        index=True
    )
    published_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    @hybrid_property
    def skill_names(self):
        return [skill.name for skill in self.skills] if self.skills else []

    @skill_names.setter
    def skill_names(self, value: list[str]) -> None:
        pass #read-only setup

    user_id: Optional[str] = Field(foreign_key="user.id", nullable=True)
    company_id: Optional[str] = Field(foreign_key="company.id", nullable=True)
    
    user: Mapped[Optional["User"]] = Relationship(
        back_populates="posts")
    
    company: Mapped[Optional["Company"]] = Relationship(
        back_populates="posts")

    skills: Mapped[List["Skill"]] = Relationship(
        back_populates="posts",
        link_model=PostSkill,
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    comments: Mapped[List[PostComment]] = Relationship(
        back_populates="post",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    reactions: Mapped[List[PostReaction]] = Relationship(
        back_populates="post",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    bookmarked_by_users: Mapped[List["User"]] = Relationship(
        back_populates="bookmarked_posts",
        link_model="Bookmark",
        sa_relationship=relationship(
            "User",
            secondary="bookmark",
            lazy="selectin",
            viewonly=True
        )
    )

    bookmarks: Mapped[List["Bookmark"]] = Relationship(
        back_populates="post",
        sa_relationship=relationship(
            "Bookmark",
            lazy="selectin",
            cascade="all, delete-orphan"
        )
    )

    is_repost: bool = Field(default=False)
    is_quote_repost: bool = Field(default=False)
    original_post_id: Optional[str] = Field(
        default=None,
        foreign_key="post.id",
        nullable=True
    )
    original_post: Optional["Post"] = Relationship(
        sa_relationship=relationship(
            "Post",
            remote_side="Post.id",
            primaryjoin="Post.original_post_id == Post.id",
            lazy="selectin"
        )
    )
    
    # Store original post information for reposts (JSON field)
    original_post_info: Optional[Dict] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True)
    )
    
    # User mentions in this post
    mentions: Mapped[List["PostMention"]] = Relationship(
        back_populates="post",
        sa_relationship_kwargs={"lazy": "selectin"}
    )


    @validator('expires_at')
    def validate_expiry(cls, v, values):
        if v and values.get('post_type') == PostType.JOB_OPPORTUNITY:
            if v <= datetime.utcnow():
                raise ValueError("Job post must expire in the future")
        return v

    @hybrid_property
    def is_active(self) -> bool:
        """ active status calculation"""
        return (
            self.status == PostStatus.PUBLISHED and
            (self.expires_at is None or self.expires_at > datetime.utcnow())
        )
    
    @is_active.expression
    def is_active(cls):
        """SQL implementation for queries"""
        return and_(
            cls.status == PostStatus.PUBLISHED,
            or_(cls.expires_at.is_(None), cls.expires_at > datetime.utcnow())
        )

    @property
    def summary(self) -> str:
        return f"{self.content[:150]}..." if len(self.content) > 150 else self.content

    def increment_views(self):
        self.engagement["view_count"] += 1


    class Config:
        arbitrary_types_allowed = True

class PostCreate(SQLModel):
    title: str
    content: str
    post_type: PostType
    industry: Optional[str] = None
    tags: Optional[List[str]] = []
    job_title: Optional[str] = None
    expires_at: Optional[datetime] = None
    media_url: Optional[str] = None
    media_urls: Optional[List[str]] = Field(default_factory=list, sa_column=Column(ARRAY(String), nullable=True))
    media_type: Optional[str] = Field(default="image")  # or "video"


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
    media_urls: Optional[List[str]] = Field(default_factory=list, sa_column=Column(ARRAY(String), nullable=True))

class PostPublic(PostCreate):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    engagement: Dict[str, int]
    is_active: bool

