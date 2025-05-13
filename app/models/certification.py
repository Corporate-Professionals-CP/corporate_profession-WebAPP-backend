from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from uuid import uuid4
from datetime import date, datetime
from sqlalchemy.orm import Mapped, relationship

class Certification(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="user.id", nullable=False)

    name: Optional[str] = None
    organization: Optional[str] = None
    url: Optional[str] = Field(default=None)
    description: Optional[str] = None
    media_url: Optional[str] = None

    issued_date: Optional[date] = None
    expiration_date: Optional[date] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)

    user: Mapped["User"] = Relationship(back_populates="certifications")
