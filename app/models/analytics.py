"""
Analytics and Insights data models
"""

from datetime import datetime
from datetime import date as Date
from typing import Optional, Dict, Any, List
from sqlmodel import SQLModel, Field, Column, JSON
from sqlalchemy import Index
from enum import Enum


class AnalyticsEventType(str, Enum):
    """Types of analytics events we track"""
    USER_SIGNUP = "user_signup"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    POST_CREATE = "post_create"
    POST_VIEW = "post_view"
    POST_LIKE = "post_like"
    POST_COMMENT = "post_comment"
    POST_SHARE = "post_share"
    CONNECTION_REQUEST = "connection_request"
    CONNECTION_ACCEPT = "connection_accept"
    MESSAGE_SENT = "message_sent"
    PROFILE_UPDATE = "profile_update"
    PROFILE_PICTURE_UPLOAD = "profile_picture_upload"
    SEARCH_PERFORMED = "search_performed"
    PAGE_VIEW = "page_view"
    SESSION_START = "session_start"
    SESSION_END = "session_end"


class UserAnalytics(SQLModel, table=True):
    """User-specific analytics data"""
    __tablename__ = "user_analytics"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    date: Date = Field(index=True)
    
    # Activity metrics
    login_count: int = Field(default=0)
    posts_created: int = Field(default=0)
    comments_made: int = Field(default=0)
    likes_given: int = Field(default=0)
    connections_made: int = Field(default=0)
    messages_sent: int = Field(default=0)
    
    # Engagement metrics
    session_duration_minutes: float = Field(default=0.0)
    page_views: int = Field(default=0)
    searches_performed: int = Field(default=0)
    
    # Profile completion
    profile_completion_score: float = Field(default=0.0)
    has_profile_picture: bool = Field(default=False)
    
    # Additional metadata
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Indexes for better query performance
    __table_args__ = (
        Index("ix_user_analytics_user_date", "user_id", "date"),
        Index("ix_user_analytics_date", "date"),
    )


class ContentAnalytics(SQLModel, table=True):
    """Content-specific analytics data"""
    __tablename__ = "content_analytics"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    post_id: str = Field(foreign_key="post.id", index=True)
    date: Date = Field(index=True)
    
    # Engagement metrics
    views: int = Field(default=0)
    likes: int = Field(default=0)
    comments: int = Field(default=0)
    shares: int = Field(default=0)
    bookmarks: int = Field(default=0)
    
    # Reach metrics
    unique_viewers: int = Field(default=0)
    click_through_rate: float = Field(default=0.0)
    
    # Virality metrics
    virality_score: float = Field(default=0.0)
    engagement_rate: float = Field(default=0.0)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PlatformAnalytics(SQLModel, table=True):
    """Platform-wide analytics data"""
    __tablename__ = "platform_analytics"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    date: Date = Field(index=True, unique=True)
    
    # User metrics
    total_users: int = Field(default=0)
    new_signups: int = Field(default=0)
    daily_active_users: int = Field(default=0)
    weekly_active_users: int = Field(default=0)
    monthly_active_users: int = Field(default=0)
    
    # Engagement metrics
    total_posts: int = Field(default=0)
    total_comments: int = Field(default=0)
    total_likes: int = Field(default=0)
    total_connections: int = Field(default=0)
    total_messages: int = Field(default=0)
    
    # Session metrics
    average_session_duration: float = Field(default=0.0)
    total_page_views: int = Field(default=0)
    
    # Geographic and demographic data
    geographic_data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    industry_data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AnalyticsEvent(SQLModel, table=True):
    """Individual analytics events for detailed tracking"""
    __tablename__ = "analytics_events"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[str] = Field(default=None, foreign_key="user.id", index=True)
    event_type: AnalyticsEventType = Field(index=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    
    # Event metadata
    properties: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    
    # User context
    ip_address: Optional[str] = Field(default=None)
    user_agent: Optional[str] = Field(default=None)
    
    # Geographic data
    country: Optional[str] = Field(default=None)
    city: Optional[str] = Field(default=None)
    
    # Session data
    session_id: Optional[str] = Field(default=None, index=True)
    
    # Additional context
    referrer: Optional[str] = Field(default=None)
    utm_source: Optional[str] = Field(default=None)
    utm_medium: Optional[str] = Field(default=None)
    utm_campaign: Optional[str] = Field(default=None)
    
    # Indexes for better query performance
    __table_args__ = (
        Index("ix_analytics_events_user_timestamp", "user_id", "timestamp"),
        Index("ix_analytics_events_type_timestamp", "event_type", "timestamp"),
        Index("ix_analytics_events_session", "session_id"),
    )


class CohortAnalytics(SQLModel, table=True):
    """Cohort analysis data for retention tracking"""
    __tablename__ = "cohort_analytics"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    cohort_month: Date = Field(index=True)  # When users signed up
    period_number: int = Field(index=True)  # How many months after signup
    
    # Cohort metrics
    users_in_cohort: int = Field(default=0)
    active_users: int = Field(default=0)
    retention_rate: float = Field(default=0.0)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
