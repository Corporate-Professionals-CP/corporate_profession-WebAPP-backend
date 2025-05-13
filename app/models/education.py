from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from uuid import uuid4
from datetime import date, datetime
from sqlalchemy.orm import Mapped, relationship

class Education(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="user.id", nullable=False)

    degree: Optional[str] = None
    school: Optional[str] = None
    location: Optional[str] = None
    url: Optional[str] = Field(default=None)
    description: Optional[str] = None
    media_url: Optional[str] = None

    from_date: Optional[date] = None
    to_date: Optional[date] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)

    user: Mapped["User"] = Relationship(back_populates="educations")
