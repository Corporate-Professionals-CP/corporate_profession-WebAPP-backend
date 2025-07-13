"""
Report and User Safety models
"""

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, String, Index, Text, JSON
from enum import Enum

if TYPE_CHECKING:
    from app.models.user import User


class ReportType(str, Enum):
    """Types of reports that can be submitted"""
    HARASSMENT = "harassment"
    SPAM = "spam"
    INAPPROPRIATE_CONTENT = "inappropriate_content"
    FAKE_PROFILE = "fake_profile"
    HATE_SPEECH = "hate_speech"
    MISINFORMATION = "misinformation"
    INTELLECTUAL_PROPERTY = "intellectual_property"
    PRIVACY_VIOLATION = "privacy_violation"
    VIOLENCE_THREATS = "violence_threats"
    ADULT_CONTENT = "adult_content"
    DISCRIMINATION = "discrimination"
    BULLYING = "bullying"
    IMPERSONATION = "impersonation"
    SCAM = "scam"
    OTHER = "other"


class ReportStatus(str, Enum):
    """Status of a report"""
    NEW = "new"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    DISMISSED = "dismissed"


class ReportPriority(str, Enum):
    """Priority levels for reports"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ContentType(str, Enum):
    """Types of content that can be reported"""
    USER_PROFILE = "user_profile"
    POST = "post"
    COMMENT = "comment"
    MESSAGE = "message"
    CONNECTION_REQUEST = "connection_request"


class OffenseType(str, Enum):
    """Types of offenses for user safety logs"""
    WARNING = "warning"
    TEMPORARY_SUSPENSION = "temporary_suspension"
    PERMANENT_BAN = "permanent_ban"
    CONTENT_REMOVAL = "content_removal"
    FEATURE_RESTRICTION = "feature_restriction"
    ACCOUNT_VERIFICATION_REQUIRED = "account_verification_required"


class Report(SQLModel, table=True):
    """User-generated reports for content moderation"""
    __tablename__ = "reports"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Reporter information
    reporter_id: str = Field(foreign_key="user.id", index=True)
    reporter_email: Optional[str] = Field(default=None)
    
    # Reported content/user
    reported_user_id: Optional[str] = Field(default=None, foreign_key="user.id", index=True)
    content_type: ContentType = Field(index=True)
    content_id: Optional[str] = Field(default=None, index=True)  # ID of the reported content
    content_url: Optional[str] = Field(default=None)
    
    # Report details
    report_type: ReportType = Field(index=True)
    title: str = Field(max_length=200)
    description: str = Field(sa_column=Column(Text))
    evidence_urls: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))  # Screenshots, links, etc.
    
    # Status and priority
    status: ReportStatus = Field(default=ReportStatus.NEW, index=True)
    priority: ReportPriority = Field(default=ReportPriority.MEDIUM, index=True)
    
    # Assignment and handling
    assigned_to: Optional[str] = Field(default=None, foreign_key="user.id")  # Admin/moderator
    assigned_at: Optional[datetime] = Field(default=None)
    
    # Resolution
    resolution_notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    resolved_at: Optional[datetime] = Field(default=None)
    resolved_by: Optional[str] = Field(default=None, foreign_key="user.id")
    
    # Escalation
    escalated_to: Optional[str] = Field(default=None, foreign_key="user.id")
    escalated_at: Optional[datetime] = Field(default=None)
    escalation_reason: Optional[str] = Field(default=None)
    
    # Metadata
    ip_address: Optional[str] = Field(default=None)
    user_agent: Optional[str] = Field(default=None)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    reporter: Optional["User"] = Relationship(
        back_populates="reports_submitted",
        sa_relationship_kwargs={"foreign_keys": "Report.reporter_id"}
    )
    reported_user: Optional["User"] = Relationship(
        back_populates="reports_received",
        sa_relationship_kwargs={"foreign_keys": "Report.reported_user_id"}
    )
    assigned_moderator: Optional["User"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "Report.assigned_to"}
    )
    resolver: Optional["User"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "Report.resolved_by"}
    )
    
    # Indexes for performance
    __table_args__ = (
        Index("ix_reports_status_priority", "status", "priority"),
        Index("ix_reports_type_status", "report_type", "status"),
        Index("ix_reports_created_status", "created_at", "status"),
        Index("ix_reports_assigned_to_status", "assigned_to", "status"),
    )


class UserOffenseLog(SQLModel, table=True):
    """Log of offenses and disciplinary actions taken against users"""
    __tablename__ = "user_offense_logs"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # User information
    user_id: str = Field(foreign_key="user.id", index=True)
    
    # Offense details
    offense_type: OffenseType = Field(index=True)
    offense_description: str = Field(sa_column=Column(Text))
    related_report_id: Optional[int] = Field(default=None, foreign_key="reports.id")
    
    # Action taken
    action_taken: str = Field(sa_column=Column(Text))
    severity_level: int = Field(default=1)  # 1-5 scale
    
    # Duration (for temporary actions)
    duration_hours: Optional[int] = Field(default=None)
    expires_at: Optional[datetime] = Field(default=None)
    
    # Decision details
    decided_by: str = Field(foreign_key="user.id")  # Admin/moderator
    decision_notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    
    # Appeal information
    appeal_submitted: bool = Field(default=False)
    appeal_notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    appeal_decided_by: Optional[str] = Field(default=None, foreign_key="user.id")
    appeal_decision: Optional[str] = Field(default=None)
    appeal_decided_at: Optional[datetime] = Field(default=None)
    
    # Status
    is_active: bool = Field(default=True, index=True)
    is_appealed: bool = Field(default=False, index=True)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user: Optional["User"] = Relationship(
        back_populates="offense_logs",
        sa_relationship_kwargs={"foreign_keys": "UserOffenseLog.user_id"}
    )
    related_report: Optional["Report"] = Relationship()
    decided_by_user: Optional["User"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "UserOffenseLog.decided_by"}
    )
    appeal_decided_by_user: Optional["User"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "UserOffenseLog.appeal_decided_by"}
    )
    
    # Indexes
    __table_args__ = (
        Index("ix_user_offense_logs_user_active", "user_id", "is_active"),
        Index("ix_user_offense_logs_type_active", "offense_type", "is_active"),
        Index("ix_user_offense_logs_severity", "severity_level", "is_active"),
    )


class ReportResolutionMetrics(SQLModel, table=True):
    """Metrics for tracking report resolution performance"""
    __tablename__ = "report_resolution_metrics"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Time period
    date: datetime = Field(index=True)
    
    # Report volumes
    total_reports: int = Field(default=0)
    new_reports: int = Field(default=0)
    resolved_reports: int = Field(default=0)
    escalated_reports: int = Field(default=0)
    dismissed_reports: int = Field(default=0)
    
    # Resolution times (in hours)
    avg_resolution_time: float = Field(default=0.0)
    median_resolution_time: float = Field(default=0.0)
    resolution_time_under_24h: int = Field(default=0)  # Count
    resolution_time_24h_to_72h: int = Field(default=0)
    resolution_time_over_72h: int = Field(default=0)
    
    # By report type
    harassment_reports: int = Field(default=0)
    spam_reports: int = Field(default=0)
    inappropriate_content_reports: int = Field(default=0)
    hate_speech_reports: int = Field(default=0)
    
    # By priority
    urgent_reports: int = Field(default=0)
    high_priority_reports: int = Field(default=0)
    medium_priority_reports: int = Field(default=0)
    low_priority_reports: int = Field(default=0)
    
    # Staff performance
    active_moderators: int = Field(default=0)
    reports_per_moderator: float = Field(default=0.0)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index("ix_report_metrics_date", "date"),
    )


class UserSafetyStatus(SQLModel, table=True):
    """Current safety status and restrictions for users"""
    __tablename__ = "user_safety_status"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # User information
    user_id: str = Field(foreign_key="user.id", index=True, unique=True)
    
    # Safety scores and flags
    trust_score: float = Field(default=100.0)  # 0-100 scale
    risk_level: str = Field(default="low")  # low, medium, high, critical
    
    # Current restrictions
    is_suspended: bool = Field(default=False, index=True)
    suspension_expires_at: Optional[datetime] = Field(default=None)
    
    is_banned: bool = Field(default=False, index=True)
    ban_reason: Optional[str] = Field(default=None)
    banned_at: Optional[datetime] = Field(default=None)
    
    # Feature restrictions
    can_post: bool = Field(default=True)
    can_comment: bool = Field(default=True)
    can_message: bool = Field(default=True)
    can_connect: bool = Field(default=True)
    
    # Verification requirements
    requires_verification: bool = Field(default=False)
    verification_type: Optional[str] = Field(default=None)
    
    # Strike system
    warning_count: int = Field(default=0)
    strike_count: int = Field(default=0)
    last_offense_at: Optional[datetime] = Field(default=None)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user: Optional["User"] = Relationship(back_populates="safety_status")
    
    # Indexes
    __table_args__ = (
        Index("ix_user_safety_status_suspended", "is_suspended", "suspension_expires_at"),
        Index("ix_user_safety_status_banned", "is_banned"),
        Index("ix_user_safety_status_trust_score", "trust_score", "risk_level"),
    )
