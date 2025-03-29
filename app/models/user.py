# app/models/user.py
import uuid
from datetime import datetime
from typing import List, Optional

from sqlmodel import SQLModel, Field, Relationship

from app.models.skill import Skill, UserSkill

def generate_uuid() -> str:
    return str(uuid.uuid4())

class User(SQLModel, table=True):
    id: str = Field(default_factory=generate_uuid, primary_key=True, index=True)
    full_name: str = Field(..., index=True)
    bio: Optional[str] = None
    job_title: str
    email: str = Field(..., index=True, unique=True)
    phone: Optional[str] = None
    industry: str  # e.g., IT, Education, Finance, Healthcare, etc.
    years_of_experience: str  # e.g., "0-2", "3-5", "6-10", "10+"
    location: str  # e.g., country/state
    age: Optional[int] = None
    sex: str  # "Male", "Female", "Prefer not to say"
    education: str
    company: str
    certifications: Optional[str] = None
    linkedin: Optional[str] = None
    cv_url: Optional[str] = None
    recruiter_tag: bool = Field(default=False)
    hide_profile: bool = Field(default=False)
    is_active: bool = Field(default=True)
    is_admin: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow}
    )

    # Relationships
    posts: List["Post"] = Relationship(back_populates="user")
    skills: List[Skill] = Relationship(back_populates="users", link_model=UserSkill)
    
    @property
    def feed_preferences(self) -> dict:
        """
        Returns a dictionary of user preferences relevant for the feed.
        Currently includes:
          - 'industry': The user's selected industry.
        This property can be expanded in the future to include other preferences like topics.
        """
        return {"industry": self.industry}

