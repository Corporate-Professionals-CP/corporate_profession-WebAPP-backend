"""
Pydantic schemas for post data validation and serialization.
Ensures API contracts match requirements.
"""

from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer
from app.schemas.user import UserPublic
from app.schemas.enums import Industry, PostType, ExperienceLevel, JobTitle, PostVisibility
from pydantic import validator


class PostBase(BaseModel):
    """Base schema containing core post fields"""
    title: str = Field(..., min_length=5, max_length=100)
    content: str = Field(..., min_length=10, max_length=2000)
    post_type: PostType
    industry: Optional[Industry] = None
    visibility: PostVisibility = Field(default=PostVisibility.PUBLIC)
    experience_level: Optional[ExperienceLevel] = None
    job_title: Optional[JobTitle] = None
    tags: Optional [List[str]] = Field(default_factory=list)
    skills: Optional [List[str]] = Field(default_factory=list)
    expires_at: Optional[datetime] = None
    media_url: Optional[str] = None
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
    title: Optional[str] = Field(None, min_length=5, max_length=100)
    content: Optional[str] = Field(None, min_length=10, max_length=2000)
    post_type: Optional[PostType] = None
    industry: Optional[Industry] = None
    experience_level: Optional[ExperienceLevel] = None
    job_title: Optional[JobTitle] = None
    skills: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    visibility: Optional[PostVisibility] = None
    expires_at: Optional[datetime] = None
    is_active: Optional[bool] = None

class ReactionBreakdown(BaseModel):
    like: int = 0
    love: int = 0
    insightful: int = 0
    funny: int = 0
    congratulations: int = 0

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
    total_reactions: int = 0
    reactions_breakdown: ReactionBreakdown | None = None


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

    @validator('skills', pre=True)
    def convert_skills(cls, v):
        if v and hasattr(v[0], 'name'):
            return [skill.name for skill in v]
        return v or []

    class Config:
        from_attributes = True
        json_encoders = {
            JobTitle: lambda v: v.value if v else None
        }

class PostSearch(BaseModel):
    """Schema for post search/filter parameters"""
    query: Optional[str] = Field(None, description="Search by keywords in title/content")
    industry: Optional[Industry] = None
    post_type: Optional[PostType] = None
    job_title: Optional[JobTitle] = None
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

