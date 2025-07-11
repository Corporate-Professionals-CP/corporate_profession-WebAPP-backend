"""
User Activity and Admin Action tracking models
"""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import uuid4
from sqlmodel import SQLModel, Field, Column, JSON
from sqlalchemy import TIMESTAMP, func


def generate_uuid() -> str:
    return str(uuid4())


class UserActivityLog(SQLModel, table=True):
    """Track user activities for admin analytics"""
    __tablename__ = "user_activity_logs"
    
    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: str = Field(foreign_key="user.id")
    activity_type: str = Field(max_length=50)  # 'login', 'post_created', 'connection_made', etc.
    activity_description: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(TIMESTAMP, server_default=func.now())
    )


class UserAdminAction(SQLModel, table=True):
    """Track admin actions performed on users"""
    __tablename__ = "user_admin_actions"
    
    id: str = Field(default_factory=generate_uuid, primary_key=True)
    user_id: str = Field(foreign_key="user.id")
    admin_id: str = Field(foreign_key="user.id")
    action_type: str = Field(max_length=50)  # 'suspended', 'activated', 'role_changed', etc.
    reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(TIMESTAMP, server_default=func.now())
    )
