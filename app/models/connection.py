from datetime import datetime
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, String
from app.schemas.enums import ConnectionStatus

class Connection(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    sender_id: str = Field(foreign_key="user.id")
    receiver_id: str = Field(foreign_key="user.id")
    
    # Store status as VARCHAR, not Enum
    status: str = Field(
        sa_column=Column(String, default=ConnectionStatus.PENDING.value)
    )
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

    sender: "User" = Relationship(sa_relationship_kwargs={"foreign_keys": "[Connection.sender_id]"})
    receiver: "User" = Relationship(sa_relationship_kwargs={"foreign_keys": "[Connection.receiver_id]"})

