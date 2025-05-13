from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, SecretStr, validator, Field, HttpUrl, field_serializer
from app.schemas.enums import (
    Industry,
    ExperienceLevel,
    Gender,
    ProfileVisibility,
    Location,
    JobTitle,
    EducationLevel
)
from app.schemas.skill import SkillRead

class UserBase(BaseModel):
    full_name: Optional[str] = Field(..., min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, pattern=r"^\+?[\d\s-]{10,15}$")
    company: Optional[str] = Field(None, min_length=2, max_length=100)
    job_title: Optional[JobTitle] = Field(None, min_length=2, max_length=100)
    bio: Optional[str] = Field(
        None,
        max_length=500,
        example="Marketing professional passionate about brand growth"
    )
    industry: Optional[Industry] = None
    years_of_experience: Optional[ExperienceLevel] = None
    location: Optional[Location] = None
    visibility: Optional[ProfileVisibility] = Field(
        default_factory=lambda: [ProfileVisibility.PUBLIC],
        description="Who should see your profile?"
    )
    topics: Optional[List[str]] = Field(
        None,
        description="Selected interest topics",
        example=["Leadership & Management", "Artificial Intelligence & Automation", "Software Engineering"]
    )
    education: Optional[EducationLevel] = None
    recruiter_tag: Optional[bool] = False

class UserCreate(UserBase):

    password: SecretStr = Field(..., min_length=8)
    password_confirmation: SecretStr


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

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

    company: Optional[str] = None
    job_title: Optional[JobTitle] = None
    bio: Optional[str] = None
    industry: Optional[Industry] = None
    years_of_experience: Optional[ExperienceLevel] = None
    location: Optional[Location] = None
    education: Optional[EducationLevel] = None
    age: Optional[int] = None
    sex: Optional[Gender] = None
    certifications: Optional[str] = None
    linkedin_profile: Optional[HttpUrl] = None
    visibility: Optional[ProfileVisibility] = None
    recruiter_tag: Optional[bool] = None
    is_admin: Optional[bool] = None
    topics: Optional [List[str]] = Field(default_factory=list)
    is_active: Optional[bool] = None

class UserPublic(UserBase):
    id: str
    industry: Optional[Industry]
    years_of_experience: Optional[ExperienceLevel]
    location: Optional[Location]
    education: Optional[EducationLevel]
    skills: List[SkillRead] = []
    profile_completion: float = Field(0.0)  # Default value
    created_at: datetime
    recruiter_tag: bool
    topics: Optional[List[str]] = Field(default_factory=list)
    visibility: Optional[ProfileVisibility]

    class Config:
        from_attributes = True
        use_enum_values = True

class UserRead(UserPublic):
    is_active: Optional[bool] = None
    is_verified: Optional[bool]
    is_admin: Optional[bool]
    updated_at: datetime

class UserDirectoryItem(BaseModel):
    id: str
    full_name: Optional[str]
    job_title: Optional[JobTitle]
    company: Optional[str]
    industry: Optional[Industry]
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
