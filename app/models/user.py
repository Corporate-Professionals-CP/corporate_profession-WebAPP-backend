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
from app.models.notification import Notification
from app.schemas.enums import (
    Industry,
    ExperienceLevel,
    Gender,
    ProfileVisibility
)

# Password hashing configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.bookmark import Bookmark
    from app.models.connection import Connection
    from app.models.reports import Report, UserOffenseLog, UserSafetyStatus


def generate_uuid() -> str:
    return str(uuid.uuid4())


class UserBase(SQLModel):
    """Base fields shared across all user schemas"""
    full_name: str = Field(..., min_length=2, max_length=100)
    email: Optional[str] = Field(None)
    phone: Optional[str] = Field(None)
    bio: Optional[str] = Field(
        None, 
        max_length=500,
        description="Professional bio/introduction"
    )
    company: Optional[str] = Field(default=None, min_length=2, max_length=100)
    job_title: Optional[str] = Field(default=None, min_length=2, max_length=100)
    industry: Optional[Industry] = Field(default=None)
    years_of_experience: Optional[ExperienceLevel] = Field(default=None)
    location: Optional[str] = Field(default=None, min_length=2, max_length=100)

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
    location: Optional[str] = Field(default=None, nullable=True)

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

    notifications: list["Notification"] = Relationship(
        back_populates="recipient",
        sa_relationship_kwargs={"foreign_keys": "[Notification.recipient_id]"}
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

    bookmarks: Mapped[List["Bookmark"]] = Relationship(
        back_populates="user",
        sa_relationship=relationship(
            "Bookmark",
            lazy="selectin",
            cascade="all, delete-orphan"
        )
    )

    bookmarked_posts: Mapped[List["Post"]] = Relationship(
        back_populates="bookmarked_by_users",
        link_model="Bookmark",
        sa_relationship=relationship(
            "Post",
            secondary="bookmark",
            lazy="selectin",
            viewonly=True
        )
    )

    connections_sent: List["Connection"] = Relationship(
        back_populates="sender",
        sa_relationship_kwargs={"foreign_keys": "[Connection.sender_id]"}
    )
    connections_received: List["Connection"] = Relationship(
        back_populates="receiver",
        sa_relationship_kwargs={"foreign_keys": "[Connection.receiver_id]"}
    )

    age: Optional[int] = Field(None, ge=18, le=100)
    profile_image_url: Optional[str] = Field(default=None, index=False)
    profile_image_uploaded_at: Optional[datetime] = Field(default=None)
    sex: Gender = Field(default=Gender.PREFER_NOT_TO_SAY)
    linkedin_profile: Optional[str] = Field(None)
    cv_url: Optional[str] = None
    status: Optional[str] = Field(default=None, max_length=255)
    cv_uploaded_at: Optional[datetime] = None
    visibility: ProfileVisibility = Field(default=ProfileVisibility.PUBLIC)
    hide_profile: bool = Field(default=False)
    recruiter_tag: bool = Field(default=False)
    is_active: bool = Field(default=True)
    is_admin: bool = Field(default=False)
    is_moderator: bool = Field(default=False)
    is_verified: bool = Field(default=False)
    hashed_password: str
    last_active_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Enhanced admin management fields
    last_login_at: Optional[datetime] = Field(default=None)
    login_count: int = Field(default=0)
    signup_source: str = Field(default="web", max_length=50)
    notes: Optional[str] = Field(default=None)  # Admin notes
    warning_count: int = Field(default=0)
    suspension_reason: Optional[str] = Field(default=None)
    suspended_at: Optional[datetime] = Field(default=None)
    suspended_by: Optional[str] = Field(default=None, foreign_key="user.id")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow}
    )

    posts: Mapped[List["Post"]] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={'lazy': 'selectin'}
    )

    # Reports and Safety relationships
    reports_submitted: List["Report"] = Relationship(
        back_populates="reporter",
        sa_relationship_kwargs={
            "foreign_keys": "[Report.reporter_id]",
            "lazy": "selectin"
        }
    )
    
    reports_received: List["Report"] = Relationship(
        back_populates="reported_user",
        sa_relationship_kwargs={
            "foreign_keys": "[Report.reported_user_id]",
            "lazy": "selectin"
        }
    )
    
    offense_logs: List["UserOffenseLog"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "foreign_keys": "[UserOffenseLog.user_id]",
            "lazy": "selectin"
        }
    )
    
    safety_status: Optional["UserSafetyStatus"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={
            "lazy": "selectin",
            "foreign_keys": "UserSafetyStatus.user_id"
        }
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
        
    def update_profile_completion(self):
        """Update profile completion percentage
        This method is called after profile updates to recalculate completion percentage
        """
        # Define field weights (total should be 100)
        required_fields = {
            'full_name': 15,
            'email': 10,
            'industry': 10,
            'location': 10,
            'job_title': 10,
            'skills': 15,
            'work_experiences': 15,
            'educations': 15,
        }

        optional_fields = {
            'years_of_experience': 5,
            'bio': 5,
            'certifications': 5,
            'linkedin_profile': 5,
            'cv_url': 5,
            'volunteering_experiences': 5,
            'company': 5,
        }

        total_score = 0

        # Check required fields
        for field, weight in required_fields.items():
            is_completed = False
            
            if field == "skills":
                is_completed = bool(self.skills and len(self.skills) > 0)
            elif field == "work_experiences":
                is_completed = bool(self.work_experiences and len(self.work_experiences) > 0)
            elif field == "educations":
                is_completed = bool(self.educations and len(self.educations) > 0)
            else:
                value = getattr(self, field, None)
                is_completed = bool(value and (not isinstance(value, str) or value.strip() != ""))

            if is_completed:
                total_score += weight

        # Check optional fields
        for field, weight in optional_fields.items():
            is_completed = False
            
            if field == "certifications":
                is_completed = bool(self.certifications and len(self.certifications) > 0)
            elif field == "volunteering_experiences":
                is_completed = bool(self.volunteering_experiences and len(self.volunteering_experiences) > 0)
            else:
                value = getattr(self, field, None)
                is_completed = bool(value and (not isinstance(value, str) or value.strip() != ""))
                
            if is_completed:
                # Only add if it won't push total_score beyond max_score
                if total_score + weight <= 100:
                    total_score += weight

        # Compute percentage and update the field
        percentage = round((total_score / 100) * 100, 2)

        # Cap percentage at 100 to satisfy validation
        if percentage > 100:
            percentage = 100.0
            
        self.profile_completion = percentage
