"""
User database model and related enumerations.
Defines the structure of user data stored in the database.
"""

import uuid
from datetime import datetime
from typing import List, Optional
from app.schemas.enums import Enum

from sqlmodel import SQLModel, Field, Relationship
from passlib.context import CryptContext

from app.models.skill import Skill, UserSkill

# Password hashing configuration using bcrypt algorithm
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class Industry(str, Enum):
    """
    Enumeration of industry options for user profiles.
    for dropdown selection.
    """
    TECH = "Tech"
    FINANCE = "Finance"
    HEALTHCARE = "Healthcare"
    EDUCATION = "Education"
    OTHER = "Other"

class ExperienceLevel(str, Enum):
    """
    Enumeration of experience level options.
    """
    ENTRY = "0-2"
    MID = "3-5"
    SENIOR = "6-10"
    EXPERT = "10+"

class Gender(str, Enum):
    """
    Enumeration of gender options with inclusive 'Prefer not to say'.
    """
    MALE = "Male"
    FEMALE = "Female"
    OTHER = "Prefer not to say"

def generate_uuid() -> str:
    """Generate a UUID string for user IDs."""
    return str(uuid.uuid4())

class User(SQLModel, table=True):
    """
    Main user model representing corporate professionals.
    Maps directly to PRD requirements.
    """
    id: str = Field(default_factory=generate_uuid, primary_key=True, index=True)
    full_name: str = Field(..., index=True)  # Required field
    bio: Optional[str] = None  # Optional personal description
    job_title: str  # Professional role (will be dropdown in UI)
    email: Optional[str] = Field(..., index=True, unique=True)  # Unique identifier
    phone: Optional[str] = None  # Optional contact
    industry: Industry  # Dropdown from Industry enum
    years_of_experience: ExperienceLevel  # PRD-specified ranges
    location: str  # Country/State
    age: Optional[int] = None  # Optional numeric input
    sex: Gender  # Gender selection from enum
    education: str  # Highest education level
    company: str  # Current organization
    certifications: Optional[str] = None  # Optional certifications
    linkedin: Optional[str] = None  # Optional profile URL
    cv_url: Optional[str] = None  # Path to uploaded CV file
    recruiter_tag: bool = Field(default=False)
    hide_profile: bool = Field(default=False)  # Privacy toggle
    is_active: bool = Field(default=True)  # Soft delete flag
    is_admin: bool = Field(default=False)  # Admin privileges
    is_verified: bool = Field(default=False)  # Email verification status
    hashed_password: str  # Never store plain text passwords
    created_at: datetime = Field(default_factory=datetime.utcnow)  # Audit field
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow}
    )  # Auto-updating timestamp

    # Relationships
    posts: List["Post"] = Relationship(back_populates="user")  # User's content posts
    skills: List[Skill] = Relationship(back_populates="users", link_model=UserSkill)  # Many-to-many with skills

    def set_password(self, password: str):
        """
        Securely hash and store user password.
        Uses passlib's bcrypt implementation.
        """
        self.hashed_password = pwd_context.hash(password)

    def verify_password(self, password: str) -> bool:
        """
        Verify provided password against stored hash.
        Returns True if match, False otherwise.
        """
        return pwd_context.verify(password, self.hashed_password)

    @property
    def feed_preferences(self) -> dict:
        """
        Returns user preferences for content feed algorithm.
        """
        return {"industry": self.industry}
