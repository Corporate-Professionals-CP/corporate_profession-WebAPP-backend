from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from uuid import UUID, uuid4

from app.schemas.enums import NotificationType

class Notification(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    recipient_id: str = Field(foreign_key="user.id")
    actor_id: Optional[str] = Field(default=None, foreign_key="user.id")

    type: NotificationType
    message: str
    is_read: bool = Field(default=False)

    post_id: Optional[str] = Field(default=None, foreign_key="post.id")
    comment_id: Optional[str] = Field(default=None, foreign_key="postcomment.id")

    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    recipient: Optional["User"] = Relationship(back_populates="notifications", sa_relationship_kwargs={"foreign_keys": "[Notification.recipient_id]"})
    actor: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Notification.actor_id]"})
    post: Optional["Post"] = Relationship()
    comment: Optional["PostComment"] = Relationship()

