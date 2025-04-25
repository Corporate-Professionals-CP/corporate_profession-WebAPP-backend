from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, SecretStr, validator, Field, HttpUrl
from app.schemas.enums import (
    Industry,
    ExperienceLevel,
    Gender,
    ProfileVisibility
)

class UserBase(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, pattern=r"^\+?[\d\s-]{10,15}$")
    username: Optional[str] = Field(None, min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    company: str = Field(..., min_length=2, max_length=100)
    job_title: str = Field(..., min_length=2, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)

class UserCreate(UserBase):
    password: SecretStr = Field(..., min_length=8)
    password_confirmation: SecretStr
    industry: Industry
    years_of_experience: ExperienceLevel
    location: str
    education: str
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")

    @validator('password')
    def validate_password(cls, v: SecretStr):
        pwd = v.get_secret_value()
        if len(pwd) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in pwd):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in pwd):
            raise ValueError("Password must contain at least one digit")
        return v

    @validator('password_confirmation')
    def passwords_match(cls, v: SecretStr, values):
        pwd = values.get('password')
        if pwd and v.get_secret_value() != pwd.get_secret_value():
            raise ValueError("Passwords do not match")
        return v

    @validator('username')
    def validate_username(cls, v: str):
        if not v.isalnum() and "_" not in v:
            raise ValueError("Username can only contain letters, numbers, and underscores")
        return v

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    username: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    bio: Optional[str] = None
    industry: Optional[Industry] = None
    years_of_experience: Optional[ExperienceLevel] = None
    location: Optional[str] = None
    education: Optional[str] = None
    age: Optional[int] = None
    sex: Optional[Gender] = None
    certifications: Optional[str] = None
    linkedin_profile: Optional[HttpUrl] = None
    visibility: Optional[ProfileVisibility] = None
    recruiter_tag: Optional[bool] = None
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None

class UserPublic(UserBase):
    id: str
    industry: Industry
    years_of_experience: ExperienceLevel
    location: str
    education: str
    skills: List[str] = Field(default_factory=list)
    profile_completion: float = Field(0.0)  # Default value
    created_at: datetime
    recruiter_tag: bool
    visibility: ProfileVisibility

    @classmethod
    def from_orm(cls, user):
        return cls(
            skills=[skill.name for skill in user.skills],
            **super().from_orm(user).dict()
        )

    class Config:
        from_attributes = True

class UserRead(UserPublic):
    is_active: bool
    is_verified: bool
    is_admin: bool
    updated_at: datetime

    @classmethod
    def from_orm(cls, user):
        base = super().from_orm(user)
        return cls(**base.dict())

class UserDirectoryItem(BaseModel):
    id: str
    full_name: str
    job_title: str
    company: str
    industry: Industry
    skills: List[str] = Field(default_factory=list)


    @classmethod
    def from_orm(cls, user):
        return cls(
            skills=[skill.name for skill in user.skills],
            **user.dict(exclude={"skills"})
        )

    class Config:
        from_attributes = True

class UserProfileCompletion(BaseModel):
    """
    Schema for profile completion status
    Profile Completion
    """
    completion_percentage: float = Field(..., ge=0, le=100)
    missing_fields: List[str] = Field(default_factory=list)
    sections: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    class Config:
        from_attributes = True
