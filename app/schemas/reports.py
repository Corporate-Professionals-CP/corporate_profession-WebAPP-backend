"""
Report and User Safety schemas
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from app.models.reports import (
    ReportType, ReportStatus, ReportPriority, ContentType, 
    OffenseType, Report, UserOffenseLog, ReportResolutionMetrics,
    UserSafetyStatus
)


# Request schemas
class ReportCreateRequest(BaseModel):
    """Schema for creating a new report"""
    reported_user_id: Optional[str] = None
    content_type: ContentType
    content_id: Optional[str] = None
    content_url: Optional[str] = None
    report_type: ReportType
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=2000)
    evidence_urls: Optional[List[str]] = None


class ReportUpdateRequest(BaseModel):
    """Schema for updating a report"""
    status: Optional[ReportStatus] = None
    priority: Optional[ReportPriority] = None
    assigned_to: Optional[str] = None
    resolution_notes: Optional[str] = None
    escalated_to: Optional[str] = None
    escalation_reason: Optional[str] = None


class ReportFilterRequest(BaseModel):
    """Schema for filtering reports"""
    status: Optional[List[ReportStatus]] = None
    report_type: Optional[List[ReportType]] = None
    priority: Optional[List[ReportPriority]] = None
    assigned_to: Optional[str] = None
    reported_user_id: Optional[str] = None
    content_type: Optional[ContentType] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


class OffenseLogCreateRequest(BaseModel):
    """Schema for creating a new offense log entry"""
    user_id: str
    offense_type: OffenseType
    offense_description: str
    related_report_id: Optional[int] = None
    action_taken: str
    severity_level: int = Field(default=1, ge=1, le=5)
    duration_hours: Optional[int] = None
    decision_notes: Optional[str] = None


class AppealSubmissionRequest(BaseModel):
    """Schema for submitting an appeal"""
    offense_log_id: int
    appeal_notes: str = Field(..., min_length=10, max_length=1000)


class AppealDecisionRequest(BaseModel):
    """Schema for deciding on an appeal"""
    offense_log_id: int
    appeal_decision: str  # "approved", "rejected", "modified"
    decision_notes: Optional[str] = None


class UserSafetyUpdateRequest(BaseModel):
    """Schema for updating user safety status"""
    trust_score: Optional[float] = Field(None, ge=0, le=100)
    risk_level: Optional[str] = Field(None, pattern="^(low|medium|high|critical)$")
    is_suspended: Optional[bool] = None
    suspension_expires_at: Optional[datetime] = None
    is_banned: Optional[bool] = None
    ban_reason: Optional[str] = None
    can_post: Optional[bool] = None
    can_comment: Optional[bool] = None
    can_message: Optional[bool] = None
    can_connect: Optional[bool] = None
    requires_verification: Optional[bool] = None
    verification_type: Optional[str] = None


# Response schemas
class ReportResponse(BaseModel):
    """Schema for report response"""
    id: int
    reporter_id: str
    reported_user_id: Optional[str]
    content_type: ContentType
    content_id: Optional[str]
    content_url: Optional[str]
    report_type: ReportType
    title: str
    description: str
    evidence_urls: Optional[List[str]]
    status: ReportStatus
    priority: ReportPriority
    assigned_to: Optional[str]
    assigned_at: Optional[datetime]
    resolution_notes: Optional[str]
    resolved_at: Optional[datetime]
    resolved_by: Optional[str]
    escalated_to: Optional[str]
    escalated_at: Optional[datetime]
    escalation_reason: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    # Additional fields for detailed view
    reporter_name: Optional[str] = None
    reported_user_name: Optional[str] = None
    assigned_moderator_name: Optional[str] = None
    resolver_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class ReportListResponse(BaseModel):
    """Schema for paginated report list"""
    reports: List[ReportResponse]
    total: int
    page: int
    limit: int
    total_pages: int
    
    # Summary statistics
    status_counts: dict = {}
    priority_counts: dict = {}
    type_counts: dict = {}


class OffenseLogResponse(BaseModel):
    """Schema for offense log response"""
    id: int
    user_id: str
    offense_type: OffenseType
    offense_description: str
    related_report_id: Optional[int]
    action_taken: str
    severity_level: int
    duration_hours: Optional[int]
    expires_at: Optional[datetime]
    decided_by: str
    decision_notes: Optional[str]
    appeal_submitted: bool
    appeal_notes: Optional[str]
    appeal_decided_by: Optional[str]
    appeal_decision: Optional[str]
    appeal_decided_at: Optional[datetime]
    is_active: bool
    is_appealed: bool
    created_at: datetime
    updated_at: datetime
    
    # Additional fields
    user_name: Optional[str] = None
    decided_by_name: Optional[str] = None
    appeal_decided_by_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class OffenseLogListResponse(BaseModel):
    """Schema for paginated offense log list"""
    offense_logs: List[OffenseLogResponse]
    total: int
    page: int
    limit: int
    total_pages: int


class UserSafetyStatusResponse(BaseModel):
    """Schema for user safety status response"""
    id: int
    user_id: str
    trust_score: float
    risk_level: str
    is_suspended: bool
    suspension_expires_at: Optional[datetime]
    is_banned: bool
    ban_reason: Optional[str]
    banned_at: Optional[datetime]
    can_post: bool
    can_comment: bool
    can_message: bool
    can_connect: bool
    requires_verification: bool
    verification_type: Optional[str]
    warning_count: int
    strike_count: int
    last_offense_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    # Additional fields
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    
    class Config:
        from_attributes = True


class ReportResolutionMetricsResponse(BaseModel):
    """Schema for report resolution metrics"""
    id: int
    date: datetime
    total_reports: int
    new_reports: int
    resolved_reports: int
    escalated_reports: int
    dismissed_reports: int
    avg_resolution_time: float
    median_resolution_time: float
    resolution_time_under_24h: int
    resolution_time_24h_to_72h: int
    resolution_time_over_72h: int
    harassment_reports: int
    spam_reports: int
    inappropriate_content_reports: int
    hate_speech_reports: int
    urgent_reports: int
    high_priority_reports: int
    medium_priority_reports: int
    low_priority_reports: int
    active_moderators: int
    reports_per_moderator: float
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ReportDashboardResponse(BaseModel):
    """Schema for report dashboard overview"""
    # Current statistics
    total_reports: int
    new_reports: int
    investigating_reports: int
    resolved_reports: int
    escalated_reports: int
    
    # Resolution performance
    avg_resolution_time_hours: float
    reports_resolved_under_24h_percent: float
    reports_resolved_under_72h_percent: float
    
    # By type
    report_type_breakdown: dict
    
    # By priority
    priority_breakdown: dict
    
    # Recent activity
    recent_reports: List[ReportResponse]
    
    # Moderator workload
    moderator_workload: dict
    
    # Trends (last 30 days)
    daily_report_counts: List[dict]
    resolution_time_trend: List[dict]
    
    # User safety overview
    total_active_users: int
    users_with_restrictions: int
    suspended_users: int
    banned_users: int
    
    # Generated timestamp
    generated_at: datetime


class UserSafetyOverviewResponse(BaseModel):
    """Schema for user safety overview"""
    user_id: str
    user_name: str
    user_email: str
    
    # Safety status
    safety_status: UserSafetyStatusResponse
    
    # Report history
    reports_submitted: int
    reports_received: int
    
    # Offense history
    offense_logs: List[OffenseLogResponse]
    
    # Recent activity
    recent_reports_submitted: List[ReportResponse]
    recent_reports_received: List[ReportResponse]
    
    # Risk assessment
    risk_factors: List[str]
    recommendations: List[str]
    
    # Generated timestamp
    generated_at: datetime
