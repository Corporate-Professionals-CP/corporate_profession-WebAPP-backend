from sqlmodel import SQLModel, Field, Relationship, Column, JSON
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from uuid import uuid4
from datetime import datetime
from sqlalchemy.orm import Mapped, relationship
from sqlalchemy import UniqueConstraint
from app.schemas.enums import ProfileVisibility

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.post import Post

class Company(SQLModel, table=True):
    """Model for company/organization pages"""
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    name: str = Field(..., min_length=2, max_length=200, index=True)
    username: str = Field(..., min_length=3, max_length=50, unique=True, index=True, description="Unique company handle (e.g., @microsoft)")
    description: Optional[str] = Field(None, max_length=2000, description="Company description/about section")
    industry: Optional[str] = Field(None, index=True)
    company_type: Optional[str] = Field(None, description="Type of company (e.g., startup, corporation, non_profit, etc.)")
    
    # Contact Information
    website: Optional[str] = Field(None)
    email: Optional[str] = Field(None)
    phone: Optional[str] = Field(None)
    
    # Location
    headquarters: Optional[str] = Field(None, description="Main headquarters location")
    locations: Optional[List[str]] = Field(default_factory=list, sa_column=Column(JSON), description="All office locations")
    
    # Company Details
    founded_year: Optional[int] = Field(None, ge=1800, le=2030)
    employee_count_range: Optional[str] = Field(None, description="e.g., '1-10', '11-50', '51-200', etc.")
    
    # Social Media & Links
    linkedin_url: Optional[str] = Field(None)
    twitter_url: Optional[str] = Field(None)
    facebook_url: Optional[str] = Field(None)
    instagram_url: Optional[str] = Field(None)
    
    # Media
    logo_url: Optional[str] = Field(None)
    cover_image_url: Optional[str] = Field(None)
    
    # Settings
    visibility: ProfileVisibility = Field(default=ProfileVisibility.PUBLIC)
    is_verified: bool = Field(default=False, description="Verified company badge")
    is_active: bool = Field(default=True)
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow}
    )
    
    # Statistics (computed fields)
    follower_count: int = Field(default=0)
    post_count: int = Field(default=0)
    
    # Relationships
    posts: Mapped[List["Post"]] = Relationship(
        back_populates="company",
        sa_relationship_kwargs={"lazy": "selectin"}
    )
    
    # Company admins/managers
    admins: Mapped[List["CompanyAdmin"]] = Relationship(
        back_populates="company",
        sa_relationship_kwargs={"lazy": "selectin"}
    )
    
    # Users following this company
    followers: Mapped[List["CompanyFollower"]] = Relationship(
        back_populates="company",
        sa_relationship_kwargs={"lazy": "selectin"}
    )

class CompanyAdmin(SQLModel, table=True):
    """Model for company page administrators"""
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    company_id: str = Field(foreign_key="company.id", nullable=False)
    user_id: str = Field(foreign_key="user.id", nullable=False)
    role: str = Field(default="admin", description="admin, manager, editor")
    permissions: Dict[str, bool] = Field(
        default_factory=lambda: {
            "can_post": True,
            "can_edit_profile": True,
            "can_manage_admins": False,
            "can_view_analytics": True
        },
        sa_column=Column(JSON)
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    company: Mapped["Company"] = Relationship(
        back_populates="admins",
        sa_relationship_kwargs={"foreign_keys": "[CompanyAdmin.company_id]"}
    )
    
    user: Mapped["User"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[CompanyAdmin.user_id]",
            "lazy": "selectin"
        }
    )

class CompanyFollower(SQLModel, table=True):
    """Model for users following companies"""
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    company_id: str = Field(foreign_key="company.id", nullable=False)
    user_id: str = Field(foreign_key="user.id", nullable=False)
    followed_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    company: Mapped["Company"] = Relationship(
        back_populates="followers",
        sa_relationship_kwargs={"foreign_keys": "[CompanyFollower.company_id]"}
    )
    
    user: Mapped["User"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[CompanyFollower.user_id]",
            "lazy": "selectin"
        }
    )
    
    class Config:
        # Ensure a user can only follow a company once
        table_args = (UniqueConstraint('company_id', 'user_id', name='unique_company_follower'),)