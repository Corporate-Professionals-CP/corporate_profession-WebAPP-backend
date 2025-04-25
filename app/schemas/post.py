"""
Pydantic schemas for post data validation and serialization.
Ensures API contracts match requirements.
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field
from app.schemas.user import UserPublic
from app.schemas.enums import Industry, PostType


class PostBase(BaseModel):
    """Base schema containing core post fields"""
    title: str = Field(..., min_length=5, max_length=100)
    content: str = Field(..., min_length=10, max_length=2000)
    post_type: PostType
    industry: Optional[Industry] = None
    tags: List[str] = Field(default_factory=list)

class PostCreate(PostBase):
    """Schema for post creation requests"""
    pass

class PostUpdate(BaseModel):
    """Schema for post updates (all fields optional)"""
    title: Optional[str] = Field(None, min_length=5, max_length=100)
    content: Optional[str] = Field(None, min_length=10, max_length=2000)
    post_type: Optional[PostType] = None
    industry: Optional[Industry] = None
    is_active: Optional[bool] = None

class PostRead(PostBase):
    """Complete post schema for API responses"""
    id: UUID
    user: Optional [UserPublic] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

class PostSearch(BaseModel):
    """Schema for post search/filter parameters"""
    query: Optional[str] = Field(None, description="Search by keywords in title/content")
    industry: Optional[Industry] = None
    post_type: Optional[PostType] = None
    created_after: Optional[datetime] = Field(
        None, 
        description="Filter posts created after this date"
    )
    limit: int = Field(100, ge=1, le=1000, description="Pagination limit")
    offset: int = Field(0, ge=0, description="Pagination offset")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "software engineer",
                "industry": Industry.TECHNOLOGY,
                "post_type": PostType.JOB_POSTING,
                "created_after": "2024-01-01T00:00:00",
                "limit": 20,
                "offset": 0
            }
        }

    class Config:
        from_attributes = True
