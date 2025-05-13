import uuid
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING, Any, Dict

from sqlmodel import SQLModel, Field, Relationship, Column, JSON
from sqlalchemy.orm import Mapped, relationship
from passlib.context import CryptContext
from app.models.contact import Contact
from app.models.follow import UserFollow
from app.models.skill import Skill, UserSkill
from app.models.education import Education
from app.models.volunteering import Volunteering
from app.models.work_experience import WorkExperience
from app.models.certification import Certification
from app.schemas.enums import (
    Industry,
    ExperienceLevel,
    Gender,
    ProfileVisibility,
    EducationLevel,
    Location,
    JobTitle
)

# Password hashing configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

if TYPE_CHECKING:
    from app.models.post import Post


def generate_uuid() -> str:
    return str(uuid.uuid4())


class UserBase(SQLModel):
    """Base fields shared across all user schemas"""
    full_name: str = Field(..., min_length=2, max_length=100)
    email: Optional[str] = Field(None, regex=r"^[^@]+@[^@]+\.[^@]+$")

    phone: Optional[str] = Field(None, regex=r"^\+?[\d\s-]{10,15}$")
    bio: Optional[str] = Field(
        None, 
        max_length=500,
        description="Professional bio/introduction"
    )
    company: Optional[str] = Field(default=None, min_length=2, max_length=100)
    job_title: Optional[str] = Field(default=None, min_length=2, max_length=100)
    industry: Optional[Industry] = Field(default=None)
    years_of_experience: Optional[ExperienceLevel] = Field(default=None)
    location: Optional[Location] = Field(default=None, min_length=2, max_length=100)
    education: Optional[EducationLevel] = Field(default=None)
    visibility: Optional[ProfileVisibility] = Field(
        default=ProfileVisibility.PUBLIC,
        description="Profile visibility preference"
    )
    topics: Optional[List[str]] = Field(
        None,
        sa_column=Column(JSON),
        description="User's selected interest topics"
    )
    profile_preferences: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="User's privacy and notification preferences"
    )



class User(UserBase, table=True):
    """Complete user model with all requirements"""
    id: str = Field(default_factory=generate_uuid, primary_key=True)

    industry: Optional[Industry] = Field(default=None, nullable=True)
    years_of_experience: Optional[ExperienceLevel] = Field(default=None, nullable=True)
    location: Optional[Location] = Field(default=None, nullable=True)
    education: Optional[EducationLevel] = Field(default=None, nullable=True)

    contacts: Mapped[List["Contact"]] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    work_experiences: Mapped[List["WorkExperience"]] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    volunteering_experiences: Mapped[List["Volunteering"]] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    educations: Mapped[List[Education]] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"lazy": "selectin"}
    )


    skills: Mapped[List["Skill"]] = Relationship(
        back_populates="users",
        link_model=UserSkill,
        sa_relationship=relationship(
            "Skill",
            secondary="userskill",
            lazy="selectin"
        )
    )

    certifications: Mapped[List["Certification"]] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    following: List["User"] = Relationship(
        back_populates="followers",
        link_model=UserFollow,
        sa_relationship_kwargs={
            "primaryjoin": "User.id == UserFollow.follower_id",
            "secondaryjoin": "User.id == UserFollow.followed_id",
            "lazy": "selectin"
        }
    )

    followers: List["User"] = Relationship(
        back_populates="following",
        link_model=UserFollow,
        sa_relationship_kwargs={
            "primaryjoin": "User.id == UserFollow.followed_id",
            "secondaryjoin": "User.id == UserFollow.follower_id",
            "lazy": "selectin"
        }
    )

    work_life_balance_prefs: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Work-life balance preferences"
    )
    mentorship_prefs: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Mentorship preferences"
    )

    age: Optional[int] = Field(None, ge=18, le=100)
    sex: Gender = Field(default=Gender.PREFER_NOT_TO_SAY)
    linkedin_profile: Optional[str] = Field(None, regex=r"^https?://(www\.)?linkedin\.com/.*$")
    cv_url: Optional[str] = None
    cv_uploaded_at: Optional[datetime] = None
    visibility: ProfileVisibility = Field(default=ProfileVisibility.PUBLIC)
    hide_profile: bool = Field(default=False)
    recruiter_tag: bool = Field(default=False)
    is_active: bool = Field(default=True)
    is_admin: bool = Field(default=False)
    is_verified: bool = Field(default=False)
    hashed_password: str
    last_active_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow}
    )

    posts: Mapped[List["Post"]] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={'lazy': 'selectin'}
    )

    profile_completion: float = Field(default=0.0, ge=0.0, le=100.0)

    def set_password(self, password: str):
        """Hash and store password securely"""
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        self.hashed_password = pwd_context.hash(password)

    def verify_password(self, password: str) -> bool:
        """Verify password against stored hash"""
        return pwd_context.verify(password, self.hashed_password)

    def update_profile_completion(self):
        """Calculate profile completion percentage"""
        required_fields = [
            'full_name', 'job_title', 'industry',
            'years_of_experience', 'location', 'education',
            'company', 'bio', 'visibility'
        ]
        optional_fields = [
            'email', 'phone', 'certifications',
            'linkedin_profile', 'cv_url', 'topics'
        ]

        completed = 0
        total_weight = len(required_fields) * 10 + len(optional_fields) * 2

        for field in required_fields:
            if getattr(self, field, None):
                completed += 10

        for field in optional_fields:
            if getattr(self, field, None):
                completed += 2

        if self.cv_url:
            completed += 10

        self.profile_completion = min(round((completed / total_weight) * 100, 2), 100)

    @property
    def public_profile(self) -> dict:
        """ Compliant public view """
        if self.visibility == ProfileVisibility.HIDDEN:
            return {"id": self.id, "name": "Hidden Profile"}

        data = {
            "id": self.id,
            "name": self.full_name,
            "job_title": self.job_title,
            "company": self.company,
            "industry": self.industry
        }

        if self.visibility == ProfileVisibility.PUBLIC:
            data.update({
                "bio": self.bio,
                "skills": [s.name for s in self.skills],
                "experience": self.years_of_experience
            })

        return data

    @property
    def recruiter_profile(self) -> dict:
        """View for recruiters """
        if not self.recruiter_tag:
            return {}

        return {
            **self.public_profile,
            "email": self.email,
            "phone": self.phone,
            "linkedin": self.linkedin_profile
        }
