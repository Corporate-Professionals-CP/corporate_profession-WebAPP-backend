from typing import List, Optional
from sqlmodel import SQLModel, Field, Relationship

class UserSkill(SQLModel, table=True):
    user_id: str = Field(foreign_key="user.id", primary_key=True)
    skill_id: int = Field(foreign_key="skill.id", primary_key=True)

class Skill(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(..., index=True, unique=True)

    # Many-to-many relationship with users
    users: List["User"] = Relationship(back_populates="skills", link_model=UserSkill)

