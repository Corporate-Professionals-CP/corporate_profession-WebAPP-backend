"""
Analytics and Insights response schemas
"""

from datetime import datetime, date
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


class TimeRange(str, Enum):
    """Time range options for analytics"""
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"
    LAST_90_DAYS = "last_90_days"
    LAST_6_MONTHS = "last_6_months"
    LAST_YEAR = "last_year"
    CUSTOM = "custom"


class MetricTrend(BaseModel):
    """Represents a metric trend over time"""
    date: date
    value: float
    percentage_change: Optional[float] = None


class UserMetricsResponse(BaseModel):
    """User metrics response"""
    total_users: int
    new_signups: int
    daily_active_users: int
    weekly_active_users: int
    monthly_active_users: int
    
    # Trends
    signup_trend: List[MetricTrend]
    dau_trend: List[MetricTrend]
    
    # Top users
    most_connected_users: List[Dict[str, Any]]
    most_active_posters: List[Dict[str, Any]]
    most_engaged_users: List[Dict[str, Any]]
    
    # Signup sources
    signup_sources: Dict[str, int]
    
    # Login frequency distribution
    login_frequency: Dict[str, int]


class EngagementMetricsResponse(BaseModel):
    """Engagement metrics response"""
    total_posts: int
    total_comments: int
    total_likes: int
    total_messages: int
    total_connections: int
    
    # Engagement trends
    posts_trend: List[MetricTrend]
    comments_trend: List[MetricTrend]
    likes_trend: List[MetricTrend]
    
    # Session metrics
    average_session_duration: float
    repeat_visit_rates: Dict[str, float]  # daily, weekly, monthly
    
    # Time on platform
    avg_time_per_session: float
    session_duration_distribution: Dict[str, int]


class ContentAnalyticsResponse(BaseModel):
    """Content analytics response"""
    post_type_distribution: Dict[str, int]
    
    # Top performing content
    most_viral_posts: List[Dict[str, Any]]
    most_commented_posts: List[Dict[str, Any]]
    most_shared_posts: List[Dict[str, Any]]
    
    # Content performance metrics
    average_engagement_rate: float
    average_virality_score: float
    
    # Post type analysis
    career_advice_posts: int
    job_posts: int
    company_updates: int
    
    # Engagement by post type
    engagement_by_post_type: Dict[str, Dict[str, float]]


class JobPostingMetricsResponse(BaseModel):
    """Job posting metrics response"""
    total_job_postings: int
    active_job_postings: int
    average_applications_per_job: float
    top_job_categories: List[Dict[str, Any]]
    job_posting_trends: Dict[str, List[Any]]
    application_conversion_rate: float
    time_to_fill: int
    generated_at: datetime


class GrowthHeatmapResponse(BaseModel):
    """Growth heatmap response"""
    geographic_usage: Dict[str, Dict[str, Any]]  # country -> metrics
    industry_usage: Dict[str, Dict[str, Any]]    # industry -> metrics
    
    # Top growing regions
    fastest_growing_countries: List[Dict[str, Any]]
    fastest_growing_industries: List[Dict[str, Any]]
    
    # Usage patterns
    usage_by_timezone: Dict[str, int]
    peak_usage_hours: List[int]


class ActivationMetricsResponse(BaseModel):
    """User activation metrics response"""
    profile_completion_rate: float
    profile_picture_upload_rate: float
    connection_request_rate: float
    
    # Activation funnel
    activation_funnel: Dict[str, Dict[str, Any]]
    
    # Time to activation
    avg_time_to_profile_completion: float
    avg_time_to_first_connection: float
    avg_time_to_first_post: float
    
    # Activation by user segment
    activation_by_industry: Dict[str, float]
    activation_by_signup_source: Dict[str, float]


class CohortAnalysisResponse(BaseModel):
    """Cohort analysis response"""
    cohort_data: List[Dict[str, Any]]
    retention_rates: Dict[str, List[float]]  # cohort -> [month1, month2, ...]
    
    # Cohort metrics
    average_retention_rate: float
    best_performing_cohort: Dict[str, Any]
    worst_performing_cohort: Dict[str, Any]
    
    # Cohort insights
    cohort_insights: List[str]


class CustomReportRequest(BaseModel):
    """Request for custom report generation"""
    name: str
    time_range: TimeRange
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    
    # Filters
    countries: Optional[List[str]] = None
    industries: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    user_segments: Optional[List[str]] = None
    
    # Metrics to include
    metrics: List[str]
    
    # Export format
    export_format: str = Field(default="json", description="Export format: json, csv, or pdf")


class CustomReportResponse(BaseModel):
    """Custom report response"""
    report_id: str
    name: str
    generated_at: datetime
    
    # Report data
    data: Dict[str, Any]
    summary: Dict[str, Any]
    
    # Export info
    export_format: str
    download_url: Optional[str] = None


class AnalyticsDashboardResponse(BaseModel):
    """Complete analytics dashboard response"""
    user_metrics: UserMetricsResponse
    engagement_metrics: EngagementMetricsResponse
    content_analytics: ContentAnalyticsResponse
    growth_heatmap: GrowthHeatmapResponse
    activation_metrics: ActivationMetricsResponse
    
    # Summary insights
    key_insights: List[str]
    recommendations: List[str]
    
    # Metadata
    generated_at: datetime
    time_range: TimeRange
    data_freshness: datetime  # When data was last updated


class AnalyticsFilterRequest(BaseModel):
    """Request filters for analytics"""
    time_range: TimeRange = TimeRange.LAST_30_DAYS
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    
    # Geographic filters
    countries: Optional[List[str]] = None
    cities: Optional[List[str]] = None
    
    # User filters
    industries: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    user_types: Optional[List[str]] = None  # recruiter, job_seeker, etc.
    
    # Content filters
    post_types: Optional[List[str]] = None
    
    # Comparison options
    compare_to_previous_period: bool = False
