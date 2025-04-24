from typing import List, Optional
from pydantic import validator
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy.orm import Mapped

class SkillBase(SQLModel):
    name: str = Field(..., max_length=50)

    @validator('name')
    def validate_skill_name(cls, v):
        v = v.strip().title()
        if not v.replace(' ', '').isalnum():
            raise ValueError("Skill names can only contain letters, numbers and spaces")
        return v

class UserSkill(SQLModel, table=True):
    """Join table for user-skill many-to-many relationship"""
    user_id: str = Field(foreign_key="user.id", primary_key=True)
    skill_id: int = Field(foreign_key="skill.id", primary_key=True)

class Skill(SkillBase, table=True):
    """Skill reference data - simple tag system"""
    id: Optional[int] = Field(default=None, primary_key=True)

    # Relationship to users (Profile skills)
    users: Mapped[List["User"]] = Relationship(
        back_populates="skills",
        link_model=UserSkill
    )
