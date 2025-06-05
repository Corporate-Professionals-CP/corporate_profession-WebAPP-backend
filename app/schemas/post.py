"""
Pydantic schemas for post data validation and serialization.
Ensures API contracts match requirements.
"""

from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer, HttpUrl
from app.schemas.user import UserPublic
from app.schemas.enums import Industry, PostType, ExperienceLevel, PostVisibility
from pydantic import validator, field_validator


class PostBase(BaseModel):
    """Base schema containing core post fields"""
    title: Optional[str] = Field(None, nullable=True)
    content: str = Field(..., min_length=10, max_length=2000)
    post_type: PostType
    industry: Optional[Industry] = None
    visibility: PostVisibility = Field(default=PostVisibility.PUBLIC)
    experience_level: Optional[ExperienceLevel] = None
    job_title: Optional[str] = None
    tags: Optional [List[str]] = Field(default_factory=list)
    skills: Optional [List[str]] = Field(default_factory=list)
    expires_at: Optional[datetime] = None
    media_urls: Optional[List[str]] = Field(
        None,
        description="Array of media URLs from /media/batch upload"
    )
    media_type: Optional[str] = Field(default="image")

    class Config:
        use_enum_values = True

class PostCreate(PostBase):
    """Schema for post creation requests"""
    @validator('expires_at')
    def validate_expires_at(cls, v, values):
        if values.get('post_type') == PostType.JOB_POSTING:
            if v is None:
                raise ValueError("Job posts must have an expiration date")
            if v <= datetime.utcnow(): 
                raise ValueError("Expiration date must be in the future")
            return v

class PostUpdate(BaseModel):
    """Schema for post updates (all fields optional)"""
    title: Optional[str] = Field(None, nullable=True)
    content: Optional[str] = Field(None, min_length=10, max_length=2000)
    post_type: Optional[PostType] = None
    industry: Optional[Industry] = None
    experience_level: Optional[ExperienceLevel] = None
    job_title: Optional[str] = None
    skills: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    media_urls: Optional[List[str]] = Field(
        None,
        description="Array of media URLs from /media/batch upload"
    )
    visibility: Optional[PostVisibility] = None
    expires_at: Optional[datetime] = None
    is_active: Optional[bool] = None

class UserReactionStatus(BaseModel):
    count: int = 0
    has_reacted: bool = False

class ReactionBreakdown(BaseModel):
    like: UserReactionStatus = Field(default_factory=lambda: UserReactionStatus())
    love: UserReactionStatus = Field(default_factory=lambda: UserReactionStatus())
    insightful: UserReactionStatus = Field(default_factory=lambda: UserReactionStatus())
    funny: UserReactionStatus = Field(default_factory=lambda: UserReactionStatus())
    congratulations: UserReactionStatus = Field(default_factory=lambda: UserReactionStatus())

class OriginalPostUser(BaseModel):
    id: UUID
    full_name: str
    job_title: Optional[str] = None

class OriginalPostInfo(BaseModel):
    id: UUID
    title: str
    content: Optional[str]
    user: OriginalPostUser

class PostRead(PostBase):
    """Complete post schema for API responses"""
    id: UUID
    user: Optional [UserPublic] = None
    username: Optional[str] = None
    skills: List[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    total_comments: int = 0
    total_reposts: int = 0
    total_reactions: int = 0
    is_bookmarked: bool = False
    media_urls: Optional[List[str]] = None
    has_reacted: bool = False
    reactions_breakdown: ReactionBreakdown = Field(default_factory=ReactionBreakdown)
    is_repost: bool = False
    original_post_id: Optional[UUID] = None
    original_post_info: Optional[OriginalPostInfo] = None


    @validator('skills', pre=True)
    def convert_skills(cls, v):
        if v and hasattr(v[0], 'name'):
            return [skill.name for skill in v]
        return v or []

    @validator('username', pre=True, always=True)
    def get_user_name(cls, v, values):
        if 'user' in values and values['user']:
            return values['user'].full_name
        return v

    @field_serializer('media_urls')
    def serialize_media_urls(self, media_urls: Optional[List[str]], _info):
        """Ensure consistent serialization of media URLs"""
        if hasattr(self, 'media_url') and self.media_url:  # Handle CSV string case
            return self.media_url.split(',')
        return media_urls or []

    class Config:
        from_attributes = True


class PostSearch(BaseModel):
    """Schema for post search/filter parameters"""
    query: Optional[str] = Field(None, description="Search by keywords in title/content")
    industry: Optional[Industry] = None
    post_type: Optional[PostType] = None
    job_title: Optional[str] = None
    experience_level: Optional[ExperienceLevel] = None
    created_after: Optional[datetime] = Field(
        None, 
        description="Filter posts created after this date"
    )

    end_date: Optional[datetime] = Field( 
        None,
        description="Filter posts created before this date"
    )
    skills: Optional[List[str]] = None
    limit: int = 100 
    cursor: Optional[str] = Field(None, description="Pagination cursor")
    media_urls: Optional[List[str]] = []

    @field_serializer("media_urls")
    def serialize_media_urls(self, media_urls: Optional[List[str]], _info):
        return media_urls or []



    class Config:
        json_schema_extra = {
            "example": {
                "query": "software engineer",
                "industry": Industry.TECHNOLOGY,
                "post_type": PostType.JOB_POSTING,
                "skills": ["Figma", "UI/UX"],
                "created_after": "2024-01-01T00:00:00",
                "limit": 20,
                "offset": 0
            }
        }


class PostSearchResponse(BaseModel):
    results: List[PostRead]
    next_cursor: Optional[str] = None
    media_urls: Optional[List[str]] = None
    media_type: Optional[str] = None

class RepostRequest(BaseModel):
    quote: Optional[str] = None
    media_urls: Optional[List[HttpUrl]] = None

    @field_serializer('media_urls')
    def serialize_media_urls(self, media_urls: Optional[List[str]], _info):
        """Ensure consistent serialization of media URLs"""
        if hasattr(self, 'media_url') and self.media_url:  # Handle CSV string case
            return self.media_url.split(',')
        return media_urls or []

    @field_validator("media_urls", mode="before")
    @classmethod
    def convert_httpurls_to_str(cls, v):
        if isinstance(v, list):
            return [str(url) if isinstance(url, HttpUrl) else url for url in v]
        return v
