from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator


class CompanyBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    username: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_-]+$')
    description: Optional[str] = Field(None, max_length=1000)
    industry: Optional[str] = Field(None, max_length=100)
    company_type: Optional[str] = Field(default="company")
    website: Optional[str] = Field(None, max_length=200)
    email: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    location: Optional[str] = Field(None, max_length=200)
    founded_year: Optional[int] = Field(None, ge=1800, le=2024)
    employee_count: Optional[str] = Field(None, max_length=50)
    linkedin_url: Optional[str] = Field(None, max_length=200)
    twitter_url: Optional[str] = Field(None, max_length=200)
    facebook_url: Optional[str] = Field(None, max_length=200)
    instagram_url: Optional[str] = Field(None, max_length=200)
    logo_url: Optional[str] = Field(None, max_length=500)
    cover_image_url: Optional[str] = Field(None, max_length=500)
    media_urls: Optional[List[str]] = Field(default_factory=list)
    is_verified: bool = Field(default=False)
    allow_posts: bool = Field(default=True)
    allow_followers: bool = Field(default=True)
    
    @validator('username')
    def validate_username(cls, v):
        if v and len(v) < 3:
            raise ValueError('Username must be at least 3 characters long')
        return v.lower() if v else v


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    industry: Optional[str] = Field(None, max_length=100)
    company_type: Optional[str] = None
    website: Optional[str] = Field(None, max_length=200)
    email: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    location: Optional[str] = Field(None, max_length=200)
    founded_year: Optional[int] = Field(None, ge=1800, le=2024)
    employee_count: Optional[str] = Field(None, max_length=50)
    linkedin_url: Optional[str] = Field(None, max_length=200)
    twitter_url: Optional[str] = Field(None, max_length=200)
    facebook_url: Optional[str] = Field(None, max_length=200)
    instagram_url: Optional[str] = Field(None, max_length=200)
    logo_url: Optional[str] = Field(None, max_length=500)
    cover_image_url: Optional[str] = Field(None, max_length=500)
    media_urls: Optional[List[str]] = None
    allow_posts: Optional[bool] = None
    allow_followers: Optional[bool] = None


class CompanyResponse(CompanyBase):
    id: str
    follower_count: int
    post_count: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CompanyAdminBase(BaseModel):
    role: str = Field(default="admin")
    permissions: Dict[str, Any] = Field(default_factory=dict)


class CompanyAdminCreate(CompanyAdminBase):
    user_id: str
    company_id: str


class CompanyAdminResponse(CompanyAdminBase):
    id: str
    user_id: str
    company_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class CompanyFollowerResponse(BaseModel):
    id: str
    user_id: str
    company_id: str
    followed_at: datetime
    
    class Config:
        from_attributes = True


class CompanySearchResponse(BaseModel):
    companies: List[CompanyResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool