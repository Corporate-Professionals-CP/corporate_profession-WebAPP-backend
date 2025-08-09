from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class PostMentionBase(BaseModel):
    mention_text: str = Field(..., min_length=1, max_length=100)
    position_start: int = Field(..., ge=0)
    position_end: int = Field(..., ge=0)
    
    class Config:
        validate_assignment = True


class PostMentionCreate(PostMentionBase):
    mentioned_user_id: str
    post_id: str
    mentioned_by_user_id: str


class PostMentionResponse(PostMentionBase):
    id: str
    mentioned_user_id: str
    post_id: str
    mentioned_by_user_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserMentionInfo(BaseModel):
    """Simplified user info for mentions"""
    id: str
    full_name: str
    username: Optional[str] = None
    profile_image_url: Optional[str] = None
    job_title: Optional[str] = None
    company: Optional[str] = None
    
    class Config:
        from_attributes = True


class MentionSuggestion(BaseModel):
    """User suggestion for @mention autocomplete"""
    id: str
    full_name: str
    username: Optional[str] = None
    profile_image_url: Optional[str] = None
    job_title: Optional[str] = None
    company: Optional[str] = None
    is_connected: bool = False
    
    class Config:
        from_attributes = True


class PostWithMentions(BaseModel):
    """Post content with parsed mentions"""
    content: str
    mentions: List[PostMentionCreate] = Field(default_factory=list)
    
    class Config:
        validate_assignment = True