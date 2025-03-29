from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    full_name: str
    bio: Optional[str] = None
    job_title: str
    email: EmailStr
    phone: Optional[str] = None
    industry: str
    years_of_experience: str  # e.g., "0-2", "3-5", "6-10", "10+"
    location: str
    age: Optional[int] = None
    sex: str  # "Male", "Female", "Prefer not to say"
    education: str
    company: str
    certifications: Optional[str] = None
    linkedin: Optional[str] = None
    cv_url: Optional[str] = None
    recruiter_tag: bool = False
    hide_profile: bool = False

class UserCreate(UserBase):
    password: str

class UserRead(UserBase):
    id: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime
    # Representing skills as list of strings (e.g., skill names)
    skills: List[str] = []

    class Config:
        orm_mode = True

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    bio: Optional[str] = None
    job_title: Optional[str] = None
    phone: Optional[str] = None
    industry: Optional[str] = None
    years_of_experience: Optional[str] = None
    location: Optional[str] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    education: Optional[str] = None
    company: Optional[str] = None
    certifications: Optional[str] = None
    linkedin: Optional[str] = None
    cv_url: Optional[str] = None
    recruiter_tag: Optional[bool] = None
    hide_profile: Optional[bool] = None
    password: Optional[str] = None


class UserPublic(BaseModel):
    id: str
    full_name: str

    class Config:
        orm_mode = True
