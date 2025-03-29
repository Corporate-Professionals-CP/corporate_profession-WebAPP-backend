import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field, Relationship

def generate_uuid() -> str:
    return str(uuid.uuid4())

class Post(SQLModel, table=True):
    id: str = Field(default_factory=generate_uuid, primary_key=True, index=True)
    user_id: str = Field(foreign_key="user.id")
    content: str
    post_type: str  # e.g., "job", "announcement", "update"
    industry: Optional[str] = Field(default=None, index=True)  # optional tag for feed filtering
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow}
    )

    # Relationship to the User model
    user: "User" = Relationship(back_populates="posts")

