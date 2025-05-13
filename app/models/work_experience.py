from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from uuid import uuid4
from datetime import datetime
from sqlalchemy import Column, Text, DateTime
from sqlalchemy.orm import Mapped, relationship
from app.schemas.enums import EmploymentType
from sqlalchemy import Enum as PgEnum

class WorkExperience(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="user.id")
    title: str = Field(index=True)
    company: str = Field(index=True)
    company_url: Optional[str] = Field(default=None)
    location: str = Field()
    employment_type: EmploymentType = Field( 
        sa_column=Column(PgEnum(EmploymentType, name="employmenttype"))
    )

    start_date: datetime = Field(
        sa_column=Column(DateTime(timezone=False))
    )
    end_date: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=False))
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.utcnow().replace(tzinfo=None),
        sa_column=Column(DateTime(timezone=False))
    )

    currently_working: bool = Field(default=False)
    description: Optional[str] = Field(sa_column=Column(Text))
    achievements: Optional[str] = Field(sa_column=Column(Text))

    user: Mapped["User"] = Relationship(back_populates="work_experiences")
