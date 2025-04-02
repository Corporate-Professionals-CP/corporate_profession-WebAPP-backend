"""
Pydantic schemas for post data validation and serialization.
Ensures API contracts match PRD requirements.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field
from app.schemas.user import UserPublic
from app.schemas.enums import Industry

class PostType(str, Enum):
    JOB_OPPORTUNITY = "job_opportunity"
    ANNOUNCEMENT = "announcement"
    PROFESSIONAL_UPDATE = "professional_update"

class PostBase(BaseModel):
    """Base schema containing core post fields"""
    title: str = Field(..., min_length=5, max_length=100)
    content: str = Field(..., min_length=10, max_length=2000)
    post_type: PostType
    industry: Optional[Industry] = None

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
    user: UserPublic
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True