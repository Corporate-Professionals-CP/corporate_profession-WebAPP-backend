from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field
from app.schemas.enums import ConnectionStatus
from app.schemas.user import UserPublic
from app.schemas.enums import ConnectionStatus, Gender, Industry, ExperienceLevel, ProfileVisibility
from app.schemas.skill import SkillRead

class ConnectionUser(BaseModel):
    id: str
    full_name: str
    headline: Optional[str] = None
    location: Optional[str] = None
    pronouns: Optional[str] = None
    industry: Optional[Industry] = None
    years_of_experience: Optional[ExperienceLevel] = None
    job_title: Optional[str] = None
    profile_image_url: Optional[str] = None
    avatar_text: Optional[str] = Field(default=None, description="Fallback initials or avatar text")
    recruiter_tag: bool = False
    created_at: Optional[datetime] = None
    connection_status: Optional[str] = Field(default="none", description="Connection status: none, connected, pending_sent, pending_received, rejected")
    action: Optional[str] = Field(default="connect", description="Available action: connect, cancel, respond, remove")

    class Config:
        from_attributes = True
        use_enum_values = True

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

class ConnectionStatsResponse(BaseModel):
    total_connections: int
    pending_requests: int
    connections: List[ConnectionRead]

class PotentialConnectionsResponse(BaseModel):
    total_connections: int
    pending_requests: int
    suggestions: List[ConnectionUser]
