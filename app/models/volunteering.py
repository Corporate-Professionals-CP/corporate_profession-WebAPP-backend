from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from uuid import uuid4
from datetime import datetime
from sqlalchemy import Column, Text
from sqlalchemy.orm import Mapped, relationship

class Volunteering(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="user.id")
    role: str = Field(index=True)
    organization: str = Field(index=True)
    organization_url: Optional[str] = Field(default=None)
    location: str = Field()
    start_date: datetime = Field()
    end_date: Optional[datetime] = Field(default=None)
    currently_volunteering: bool = Field(default=False)
    description: Optional[str] = Field(sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    user: Mapped["User"] = Relationship(back_populates="volunteering_experiences")
