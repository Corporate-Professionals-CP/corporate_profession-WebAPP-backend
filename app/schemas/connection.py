from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel
from app.schemas.enums import ConnectionStatus
from app.schemas.user import UserPublic


class ConnectionUser(BaseModel):
    id: str
    full_name: str

class ConnectionCreate(BaseModel):
    receiver_id: UUID

class ConnectionRead(BaseModel):
    id: UUID
    sender_id: UUID
    receiver_id: UUID
    status: str
    created_at: datetime
    sender: ConnectionUser 
    receiver: ConnectionUser

    class Config:
        from_attributes = True

class ConnectionUpdate(BaseModel):
    status: ConnectionStatus

