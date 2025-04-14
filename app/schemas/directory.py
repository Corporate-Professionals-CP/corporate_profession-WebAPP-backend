from typing import Optional
from pydantic import BaseModel
from app.schemas.enums import Industry, ExperienceLevel

class LocationFilter(BaseModel):
    """Structured location filtering"""
    country: Optional[str] = None
    state: Optional[str] = None

class DirectorySearchParams(BaseModel):
    """Search parameters for professional directory"""
    q: Optional[str] = None  # Combined search field
    industry: Optional[Industry] = None
    experience: Optional[ExperienceLevel] = None
    location: Optional[LocationFilter] = None
    skill: Optional[str] = None
    recruiter_only: Optional[bool] = False
    
    class Config:
        use_enum_values = True

class UserDirectoryItem(BaseModel):
    """Minimal user data for directory listings"""
    id: str
    full_name: str
    job_title: Optional[str]
    company: Optional[str]
    industry: Optional[str]
    is_recruiter: bool
    
    class Config:
        from_attributes = True
