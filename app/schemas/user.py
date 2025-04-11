"""
User schemas fully aligned with requirements
- (Profile Creation & Management)
- (Security & Privacy)
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, EmailStr, SecretStr, validator, Field, HttpUrl
from app.models.user import Industry, ExperienceLevel, Gender

class UserBase(BaseModel):
    """
    Base user schema matching all profile fields
    """
    full_name: str = Field(..., min_length=1, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    job_title: str = Field(..., max_length=100)
    email: Optional[EmailStr] = Field(None)  # Email is optional
    phone: Optional[str] = Field(None, regex=r"^\+?[1-9]\d{1,14}$")  # E.164 format
    industry: Industry
    years_of_experience: ExperienceLevel
    location: str = Field(..., max_length=100)
    age: Optional[int] = Field(None, ge=18, le=100)  # Reasonable age range
    sex: Gender
    education: str = Field(..., max_length=100)
    company: str = Field(..., max_length=100)
    certifications: Optional[str] = Field(None, max_length=200)
    linkedin: Optional[HttpUrl] = None  # Proper URL validation
    recruiter_tag: bool = Field(False)
    hide_profile: bool = Field(False)  # privacy setting

class UserCreate(UserBase):
    """
    User registration schema with password validation
    Secure registration with email verification
    """
    password: SecretStr = Field(..., min_length=8)
    password_confirmation: SecretStr

    @validator('password')
    def validate_password_complexity(cls, v):
        """Enforce password complexity requirements"""
        password = v.get_secret_value()
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in password):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in password):
            raise ValueError("Password must contain at least one digit")
        return v

    @validator('password_confirmation')
    def passwords_match(cls, v, values):
        """Ensure password confirmation matches"""
        if 'password' in values and v != values['password']:
            raise ValueError("Passwords do not match")
        return v

class UserRead(UserBase):
    """
    Complete user schema for API responses
    Fields plus system fields
    """
    id: str  # UUID
    is_active: bool
    is_verified: bool  # email verification
    is_admin: bool = False
    created_at: datetime
    updated_at: datetime
    skills: List[str] = Field(default_factory=list)  # 2.2 skills
    cv_url: Optional[str] = None  # CV upload

    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class UserUpdate(BaseModel):
    """
    Profile update schema with partial updates
    All fields should be updatable
    """
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    job_title: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, regex=r"^\+?[1-9]\d{1,14}$")
    industry: Optional[Industry] = None
    years_of_experience: Optional[ExperienceLevel] = None
    location: Optional[str] = Field(None, max_length=100)
    age: Optional[int] = Field(None, ge=18, le=100)
    sex: Optional[Gender] = None
    education: Optional[str] = Field(None, max_length=100)
    company: Optional[str] = Field(None, max_length=100)
    certifications: Optional[str] = Field(None, max_length=200)
    linkedin: Optional[HttpUrl] = None
    recruiter_tag: Optional[bool] = None
    hide_profile: Optional[bool] = None

class UserPublic(BaseModel):
    """
    GDPR-compliant public profile view
    Minimal info when profile is hidden
    """
    id: str
    full_name: str
    job_title: Optional[str] = None
    industry: Optional[str] = None
    company: Optional[str] = None
    recruiter_tag: bool  # Always show recruiter tag

    @classmethod
    def from_user(cls, user: 'User'):
        """Respect privacy settings"""
        if user.hide_profile:
            return cls(
                id=user.id,
                full_name=user.full_name,
                recruiter_tag=user.recruiter_tag
            )
        return cls(
            id=user.id,
            full_name=user.full_name,
            job_title=user.job_title,
            industry=user.industry.value if user.industry else None,
            company=user.company,
            recruiter_tag=user.recruiter_tag
        )

    class Config:
        orm_mode = True

class UserProfileCompletion(BaseModel):
    """
    Schema for profile completion status
    Show profile completion percentage
    """
    completion_percentage: float = Field(..., ge=0, le=100)
    missing_fields: List[str] = Field(default_factory=list)
