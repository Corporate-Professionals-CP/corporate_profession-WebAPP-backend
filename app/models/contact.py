from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from uuid import uuid4
from datetime import datetime
from app.schemas.enums import ContactType
from sqlalchemy import Column, Enum as PgEnum
from sqlalchemy.orm import Mapped, relationship

class Contact(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="user.id")
    type: ContactType = Field(
        sa_column=Column(PgEnum(ContactType, name="contacttype"))
    )
    platform_name: Optional[str] = Field(default=None)
    username: Optional[str] = Field(default=None)
    url: str = Field()
    created_at: datetime = Field(default_factory=datetime.utcnow)

    user: Mapped["User"] = Relationship(back_populates="contacts")

