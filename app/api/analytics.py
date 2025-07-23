"""
Analytics and Insights API endpoints
"""

import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import json
import csv
import io
from pathlib import Path

from app.db.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.crud.analytics import AnalyticsService
from app.schemas.analytics import (
    AnalyticsDashboardResponse,
    UserMetricsResponse,
    EngagementMetricsResponse,
    ContentAnalyticsResponse,
    GrowthHeatmapResponse,
    ActivationMetricsResponse,
    CohortAnalysisResponse,
    CustomReportRequest,
    CustomReportResponse,
    AnalyticsFilterRequest,
    TimeRange,
    JobPostingMetricsResponse
)
from app.models.analytics import AnalyticsEventType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/job-posting-metrics", response_model=JobPostingMetricsResponse)
async def get_job_posting_metrics(
    time_range: TimeRange = Query(TimeRange.LAST_30_DAYS),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    industries: Optional[List[str]] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get job posting metrics and analytics"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )
    
    try:
        analytics_service = AnalyticsService(db)
        filters = AnalyticsFilterRequest(
            time_range=time_range,
            start_date=start_date,
            end_date=end_date,
            industries=industries
        )
        
        # Get job posting metrics
        job_metrics = await analytics_service.get_job_posting_metrics(filters)
        
        return {
            "total_job_postings": job_metrics.get("total_job_postings", 0),
            "active_job_postings": job_metrics.get("active_job_postings", 0),
            "average_applications_per_job": job_metrics.get("average_applications_per_job", 0),
            "top_job_categories": job_metrics.get("top_job_categories", []),
            "job_posting_trends": job_metrics.get("job_posting_trends", {}),
            "application_conversion_rate": job_metrics.get("application_conversion_rate", 0),
            "time_to_fill": job_metrics.get("time_to_fill", 0),
            "generated_at": datetime.utcnow()
        }
        
    except Exception as e:
        logger.error(f"Error fetching job posting metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch job posting metrics"
        )

@router.get("/dashboard", response_model=AnalyticsDashboardResponse)
async def get_analytics_dashboard(
    time_range: TimeRange = Query(TimeRange.LAST_30_DAYS),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    countries: Optional[List[str]] = Query(None),
    industries: Optional[List[str]] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get complete analytics dashboard data
    Requires admin privileges
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )
    
    try:
        analytics_service = AnalyticsService(db)
        
        # Create filter request
        filters = AnalyticsFilterRequest(
            time_range=time_range,
            start_date=start_date,
            end_date=end_date,
            countries=countries,
            industries=industries
        )
        
        # Get all analytics data
        user_metrics = await analytics_service.get_user_metrics(filters)
        engagement_metrics = await analytics_service.get_engagement_metrics(filters)
        content_analytics = await analytics_service.get_content_analytics(filters)
        activation_metrics = await analytics_service.get_activation_metrics(filters)
        cohort_analysis = await analytics_service.get_cohort_analysis(filters)
        
        # Generate key insights
        key_insights = await _generate_key_insights(
            user_metrics, engagement_metrics, content_analytics, activation_metrics
        )
        
        # Generate recommendations
        recommendations = await _generate_recommendations(
            user_metrics, engagement_metrics, activation_metrics
        )
        
        return AnalyticsDashboardResponse(
            user_metrics=UserMetricsResponse(**user_metrics),
            engagement_metrics=EngagementMetricsResponse(**engagement_metrics),
            content_analytics=ContentAnalyticsResponse(**content_analytics),
            growth_heatmap=GrowthHeatmapResponse(
                geographic_usage={},
                industry_usage={},
                fastest_growing_countries=[],
                fastest_growing_industries=[],
                usage_by_timezone={},
                peak_usage_hours=[]
            ),
            activation_metrics=ActivationMetricsResponse(**activation_metrics),
            key_insights=key_insights,
            recommendations=recommendations,
            generated_at=datetime.utcnow(),
            time_range=time_range,
            data_freshness=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Error generating analytics dashboard: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate analytics dashboard"
        )


@router.get("/user-metrics", response_model=UserMetricsResponse)
async def get_user_metrics(
    time_range: TimeRange = Query(TimeRange.LAST_30_DAYS),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get user metrics and trends"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )
    
    try:
        analytics_service = AnalyticsService(db)
        filters = AnalyticsFilterRequest(
            time_range=time_range,
            start_date=start_date,
            end_date=end_date
        )
        
        metrics = await analytics_service.get_user_metrics(filters)
        return UserMetricsResponse(**metrics)
        
    except Exception as e:
        logger.error(f"Error fetching user metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user metrics"
        )


@router.get("/engagement-metrics", response_model=EngagementMetricsResponse)
async def get_engagement_metrics(
    time_range: TimeRange = Query(TimeRange.LAST_30_DAYS),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get engagement metrics and trends"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )
    
    try:
        analytics_service = AnalyticsService(db)
        filters = AnalyticsFilterRequest(
            time_range=time_range,
            start_date=start_date,
            end_date=end_date
        )
        
        metrics = await analytics_service.get_engagement_metrics(filters)
        return EngagementMetricsResponse(**metrics)
        
    except Exception as e:
        logger.error(f"Error fetching engagement metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch engagement metrics"
        )


@router.get("/content-analytics", response_model=ContentAnalyticsResponse)
async def get_content_analytics(
    time_range: TimeRange = Query(TimeRange.LAST_30_DAYS),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get content analytics and performance metrics"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )
    
    try:
        analytics_service = AnalyticsService(db)
        filters = AnalyticsFilterRequest(
            time_range=time_range,
            start_date=start_date,
            end_date=end_date
        )
        
        analytics = await analytics_service.get_content_analytics(filters)
        return ContentAnalyticsResponse(**analytics)
        
    except Exception as e:
        logger.error(f"Error fetching content analytics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch content analytics"
        )


@router.get("/activation-metrics", response_model=ActivationMetricsResponse)
async def get_activation_metrics(
    time_range: TimeRange = Query(TimeRange.LAST_30_DAYS),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get user activation metrics"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )
    
    try:
        analytics_service = AnalyticsService(db)
        filters = AnalyticsFilterRequest(
            time_range=time_range,
            start_date=start_date,
            end_date=end_date
        )
        
        metrics = await analytics_service.get_activation_metrics(filters)
        return ActivationMetricsResponse(**metrics)
        
    except Exception as e:
        logger.error(f"Error fetching activation metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch activation metrics"
        )


@router.get("/cohort-analysis", response_model=CohortAnalysisResponse)
async def get_cohort_analysis(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get cohort analysis and retention data"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )
    
    try:
        analytics_service = AnalyticsService(db)
        filters = AnalyticsFilterRequest()  # Use default filters for cohort analysis
        
        analysis = await analytics_service.get_cohort_analysis(filters)
        return CohortAnalysisResponse(**analysis)
        
    except Exception as e:
        logger.error(f"Error fetching cohort analysis: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch cohort analysis"
        )


@router.post("/custom-report", response_model=CustomReportResponse)
async def generate_custom_report(
    report_request: CustomReportRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Generate a custom analytics report"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )
    
    try:
        report_id = str(uuid.uuid4())
        
        # Add background task to generate report
        background_tasks.add_task(
            _generate_custom_report_background,
            report_id,
            report_request,
            db,
            current_user.id
        )
        
        return CustomReportResponse(
            report_id=report_id,
            name=report_request.name,
            generated_at=datetime.utcnow(),
            data={},
            summary={},
            export_format=report_request.export_format,
            download_url=f"/analytics/reports/{report_id}/download"
        )
        
    except Exception as e:
        logger.error(f"Error generating custom report: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate custom report"
        )


@router.get("/reports/{report_id}/download")
async def download_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Download a generated report"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )
    
    try:
        # Check if report exists
        report_path = Path(f"/tmp/reports/{report_id}")
        if not report_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found"
            )
        
        return FileResponse(
            path=str(report_path),
            filename=f"analytics_report_{report_id}.csv",
            media_type="text/csv"
        )
        
    except Exception as e:
        logger.error(f"Error downloading report: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download report"
        )


@router.post("/track-event")
async def track_analytics_event(
    event_type: AnalyticsEventType,
    properties: Dict[str, Any] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Track an analytics event"""
    try:
        analytics_service = AnalyticsService(db)
        
        await analytics_service.track_event(
            event_type=event_type,
            user_id=current_user.id,
            properties=properties or {}
        )
        
        return {"message": "Event tracked successfully"}
        
    except Exception as e:
        logger.error(f"Error tracking event: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to track event"
        )


# Manual trigger endpoints for analytics tasks
@router.post("/trigger-daily-analytics")
async def trigger_daily_analytics_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Manually trigger daily analytics computation"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )
    
    try:
        from app.utils.analytics_scheduler import trigger_daily_analytics
        await trigger_daily_analytics()
        return {"message": "Daily analytics tasks triggered successfully"}
    except Exception as e:
        logger.error(f"Error triggering daily analytics: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to trigger daily analytics tasks"
        )


@router.post("/trigger-weekly-analytics")
async def trigger_weekly_analytics_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Manually trigger weekly analytics computation"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )
    
    try:
        from app.utils.analytics_scheduler import trigger_weekly_analytics
        await trigger_weekly_analytics()
        return {"message": "Weekly analytics tasks triggered successfully"}
    except Exception as e:
        logger.error(f"Error triggering weekly analytics: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to trigger weekly analytics tasks"
        )


# Helper functions
async def _generate_key_insights(
    user_metrics: Dict[str, Any],
    engagement_metrics: Dict[str, Any],
    content_analytics: Dict[str, Any],
    activation_metrics: Dict[str, Any]
) -> List[str]:
    """Generate key insights from analytics data"""
    insights = []
    
    # User growth insights
    if user_metrics.get("new_signups", 0) > 0:
        insights.append(f"Platform gained {user_metrics['new_signups']} new users")
    
    # Engagement insights
    if engagement_metrics.get("total_posts", 0) > 0:
        insights.append(f"Users created {engagement_metrics['total_posts']} posts")
    
    # Activation insights
    completion_rate = activation_metrics.get("profile_completion_rate", 0)
    if completion_rate > 0:
        insights.append(f"{completion_rate:.1f}% of new users completed their profiles")
    
    return insights


async def _generate_recommendations(
    user_metrics: Dict[str, Any],
    engagement_metrics: Dict[str, Any],
    activation_metrics: Dict[str, Any]
) -> List[str]:
    """Generate recommendations based on analytics data"""
    recommendations = []
    
    # Profile completion recommendations
    completion_rate = activation_metrics.get("profile_completion_rate", 0)
    if completion_rate < 50:
        recommendations.append("Consider improving onboarding flow to increase profile completion rate")
    
    # Engagement recommendations
    if engagement_metrics.get("average_session_duration", 0) < 5:
        recommendations.append("Focus on content quality to increase user session duration")
    
    # Growth recommendations
    if user_metrics.get("daily_active_users", 0) < user_metrics.get("weekly_active_users", 0) * 0.3:
        recommendations.append("Implement daily engagement features to improve DAU/WAU ratio")
    
    return recommendations


async def _generate_custom_report_background(
    report_id: str,
    report_request: CustomReportRequest,
    db: AsyncSession,
    user_id: str
):
    """Background task to generate custom report"""
    try:
        analytics_service = AnalyticsService(db)
        
        # Convert request to filters
        filters = AnalyticsFilterRequest(
            time_range=report_request.time_range,
            start_date=report_request.start_date,
            end_date=report_request.end_date,
            countries=report_request.countries,
            industries=report_request.industries
        )
        
        # Generate report data based on requested metrics
        report_data = {}
        
        if "user_metrics" in report_request.metrics:
            report_data["user_metrics"] = await analytics_service.get_user_metrics(filters)
        
        if "engagement_metrics" in report_request.metrics:
            report_data["engagement_metrics"] = await analytics_service.get_engagement_metrics(filters)
        
        if "content_analytics" in report_request.metrics:
            report_data["content_analytics"] = await analytics_service.get_content_analytics(filters)
        
        if "activation_metrics" in report_request.metrics:
            report_data["activation_metrics"] = await analytics_service.get_activation_metrics(filters)
        
        # Save report to file
        report_path = Path(f"/tmp/reports/{report_id}")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        if report_request.export_format == "csv":
            await _save_report_as_csv(report_data, report_path)
        elif report_request.export_format == "json":
            await _save_report_as_json(report_data, report_path)
        
        logger.info(f"Custom report {report_id} generated successfully")
        
    except Exception as e:
        logger.error(f"Error generating custom report {report_id}: {str(e)}")


async def _save_report_as_csv(report_data: Dict[str, Any], report_path: Path):
    """Save report data as CSV"""
    with open(report_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # Write headers
        writer.writerow(["Metric", "Value"])
        
        # Write data
        for section, data in report_data.items():
            writer.writerow([section.upper(), ""])
            for key, value in data.items():
                if isinstance(value, (int, float, str)):
                    writer.writerow([key, value])


async def _save_report_as_json(report_data: Dict[str, Any], report_path: Path):
    """Save report data as JSON"""
    with open(report_path, 'w', encoding='utf-8') as jsonfile:
        json.dump(report_data, jsonfile, indent=2, default=str)
