"""
Reports and User Safety API endpoints
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
import math

from app.db.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.crud.reports import ReportsService
from app.schemas.reports import (
    ReportCreateRequest, ReportUpdateRequest, ReportFilterRequest,
    ReportResponse, ReportListResponse, ReportDashboardResponse,
    OffenseLogCreateRequest, OffenseLogResponse, OffenseLogListResponse,
    AppealSubmissionRequest, AppealDecisionRequest,
    UserSafetyUpdateRequest, UserSafetyStatusResponse, UserSafetyOverviewResponse,
    ReportResolutionMetricsResponse
)
from app.models.reports import ReportStatus, ReportPriority, ReportType, OffenseType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["Reports & User Safety"])


# Report Management Endpoints
@router.post("/", response_model=ReportResponse)
async def create_report(
    report_data: ReportCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new report"""
    try:
        reports_service = ReportsService(db)
        
        # Get IP address and user agent
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        report = await reports_service.create_report(
            report_data=report_data,
            reporter_id=current_user.id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Convert to response format
        report_response = ReportResponse.model_validate(report)
        
        # Add user names for display
        if report.reporter:
            report_response.reporter_name = report.reporter.full_name
        if report.reported_user:
            report_response.reported_user_name = report.reported_user.full_name
        
        return report_response
        
    except Exception as e:
        logger.error(f"Error creating report: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create report"
        )


@router.get("/", response_model=ReportListResponse)
async def get_reports(
    status: Optional[List[ReportStatus]] = Query(None),
    report_type: Optional[List[ReportType]] = Query(None),
    priority: Optional[List[ReportPriority]] = Query(None),
    assigned_to: Optional[str] = Query(None),
    reported_user_id: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get reports with filtering and pagination (Admin/Moderator only)"""
    if not current_user.is_admin and not current_user.is_moderator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin or Moderator privileges required."
        )
    
    try:
        reports_service = ReportsService(db)
        
        filters = ReportFilterRequest(
            status=status,
            report_type=report_type,
            priority=priority,
            assigned_to=assigned_to,
            reported_user_id=reported_user_id,
            date_from=date_from,
            date_to=date_to,
            page=page,
            limit=limit
        )
        
        reports, total = await reports_service.get_reports(filters)
        
        # Convert to response format
        report_responses = []
        for report in reports:
            report_response = ReportResponse.model_validate(report)
            
            # Add user names for display
            if report.reporter:
                report_response.reporter_name = report.reporter.full_name
            if report.reported_user:
                report_response.reported_user_name = report.reported_user.full_name
            if report.assigned_moderator:
                report_response.assigned_moderator_name = report.assigned_moderator.full_name
            if report.resolver:
                report_response.resolver_name = report.resolver.full_name
            
            report_responses.append(report_response)
        
        # Calculate summary statistics
        status_counts = {}
        priority_counts = {}
        type_counts = {}
        
        for report in reports:
            status_counts[report.status.value] = status_counts.get(report.status.value, 0) + 1
            priority_counts[report.priority.value] = priority_counts.get(report.priority.value, 0) + 1
            type_counts[report.report_type.value] = type_counts.get(report.report_type.value, 0) + 1
        
        total_pages = math.ceil(total / limit)
        
        return ReportListResponse(
            reports=report_responses,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
            status_counts=status_counts,
            priority_counts=priority_counts,
            type_counts=type_counts
        )
        
    except Exception as e:
        logger.error(f"Error getting reports: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve reports"
        )


@router.get("/dashboard", response_model=ReportDashboardResponse)
async def get_report_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get report dashboard data (Admin only)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )
    
    try:
        reports_service = ReportsService(db)
        dashboard_data = await reports_service.get_report_dashboard_data()
        
        # Convert recent reports to response format
        recent_reports = []
        for report in dashboard_data.get('recent_reports', []):
            report_response = ReportResponse.model_validate(report)
            if report.reporter:
                report_response.reporter_name = report.reporter.full_name
            if report.reported_user:
                report_response.reported_user_name = report.reported_user.full_name
            recent_reports.append(report_response)
        
        dashboard_data['recent_reports'] = recent_reports
        
        return ReportDashboardResponse(**dashboard_data)
        
    except Exception as e:
        logger.error(f"Error getting report dashboard: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve dashboard data"
        )


@router.get("/metrics", response_model=List[ReportResolutionMetricsResponse])
async def get_report_metrics(
    date_from: datetime = Query(..., description="Start date for metrics"),
    date_to: datetime = Query(..., description="End date for metrics"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get report resolution metrics (Admin only)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )
    
    try:
        # Convert timezone-aware datetimes to timezone-naive for database compatibility
        if date_from.tzinfo is not None:
            date_from = date_from.replace(tzinfo=None)
        if date_to.tzinfo is not None:
            date_to = date_to.replace(tzinfo=None)
            
        reports_service = ReportsService(db)
        metrics = await reports_service.get_report_metrics(date_from, date_to)
        
        return [ReportResolutionMetricsResponse.model_validate(metric) for metric in metrics]
        
    except Exception as e:
        logger.error(f"Error getting report metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve metrics"
        )


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific report (Admin/Moderator only)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )
    
    try:
        reports_service = ReportsService(db)
        report = await reports_service.get_report(report_id)
        
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found"
            )
        
        report_response = ReportResponse.model_validate(report)
        
        # Add user names for display
        if report.reporter:
            report_response.reporter_name = report.reporter.full_name
        if report.reported_user:
            report_response.reported_user_name = report.reported_user.full_name
        if report.assigned_moderator:
            report_response.assigned_moderator_name = report.assigned_moderator.full_name
        if report.resolver:
            report_response.resolver_name = report.resolver.full_name
        
        return report_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting report {report_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve report"
        )


@router.put("/{report_id}", response_model=ReportResponse)
async def update_report(
    report_id: int,
    update_data: ReportUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update a report (Admin/Moderator only)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )
    
    try:
        reports_service = ReportsService(db)
        report = await reports_service.update_report(
            report_id=report_id,
            update_data=update_data,
            updated_by=current_user.id
        )
        
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found"
            )
        
        report_response = ReportResponse.model_validate(report)
        
        # Add user names for display
        if report.reporter:
            report_response.reporter_name = report.reporter.full_name
        if report.reported_user:
            report_response.reported_user_name = report.reported_user.full_name
        if report.assigned_moderator:
            report_response.assigned_moderator_name = report.assigned_moderator.full_name
        if report.resolver:
            report_response.resolver_name = report.resolver.full_name
        
        return report_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating report {report_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update report"
        )


@router.post("/{report_id}/assign")
async def assign_report(
    report_id: int,
    assigned_to: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Assign a report to a moderator (Admin only)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )
    
    try:
        reports_service = ReportsService(db)
        report = await reports_service.assign_report(
            report_id=report_id,
            assigned_to=assigned_to,
            assigned_by=current_user.id
        )
        
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found"
            )
        
        return {"message": "Report assigned successfully", "report_id": report_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning report {report_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign report"
        )


@router.post("/{report_id}/resolve")
async def resolve_report(
    report_id: int,
    resolution_notes: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Resolve a report (Admin/Moderator only)"""
    if not current_user.is_admin and not current_user.is_moderator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin or Moderator privileges required."
        )
    
    try:
        reports_service = ReportsService(db)
        report = await reports_service.resolve_report(
            report_id=report_id,
            resolution_notes=resolution_notes,
            resolved_by=current_user.id
        )
        
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found"
            )
        
        return {"message": "Report resolved successfully", "report_id": report_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving report {report_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resolve report"
        )


@router.post("/{report_id}/escalate")
async def escalate_report(
    report_id: int,
    escalated_to: str,
    escalation_reason: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Escalate a report (Admin/Moderator only)"""
    if not current_user.is_admin and not current_user.is_moderator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin or Moderator privileges required."
        )
    
    try:
        reports_service = ReportsService(db)
        report = await reports_service.escalate_report(
            report_id=report_id,
            escalated_to=escalated_to,
            escalation_reason=escalation_reason,
            escalated_by=current_user.id
        )
        
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found"
            )
        
        return {"message": "Report escalated successfully", "report_id": report_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error escalating report {report_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to escalate report"
        )


# User Offense Management Endpoints
@router.post("/offense-logs", response_model=OffenseLogResponse)
async def create_offense_log(
    offense_data: OffenseLogCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new offense log entry (Admin only)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )
    
    try:
        reports_service = ReportsService(db)
        offense_log = await reports_service.create_offense_log(
            offense_data=offense_data,
            decided_by=current_user.id
        )
        
        offense_response = OffenseLogResponse.model_validate(offense_log)
        
        # Add user names for display
        if offense_log.user:
            offense_response.user_name = offense_log.user.full_name
        if offense_log.decided_by_user:
            offense_response.decided_by_name = offense_log.decided_by_user.full_name
        
        return offense_response
        
    except Exception as e:
        logger.error(f"Error creating offense log: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create offense log"
        )


@router.get("/offense-logs/{user_id}", response_model=OffenseLogListResponse)
async def get_user_offense_logs(
    user_id: str,
    include_inactive: bool = Query(False),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get offense logs for a user (Admin only)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )
    
    try:
        reports_service = ReportsService(db)
        offense_logs = await reports_service.get_user_offense_logs(
            user_id=user_id,
            include_inactive=include_inactive
        )
        
        # Apply pagination
        total = len(offense_logs)
        start = (page - 1) * limit
        end = start + limit
        paginated_logs = offense_logs[start:end]
        
        # Convert to response format
        offense_responses = []
        for offense_log in paginated_logs:
            offense_response = OffenseLogResponse.model_validate(offense_log)
            
            # Add user names for display
            if offense_log.user:
                offense_response.user_name = offense_log.user.full_name
            if offense_log.decided_by_user:
                offense_response.decided_by_name = offense_log.decided_by_user.full_name
            if offense_log.appeal_decided_by_user:
                offense_response.appeal_decided_by_name = offense_log.appeal_decided_by_user.full_name
            
            offense_responses.append(offense_response)
        
        total_pages = math.ceil(total / limit)
        
        return OffenseLogListResponse(
            offense_logs=offense_responses,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Error getting offense logs for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve offense logs"
        )


@router.post("/appeals", response_model=OffenseLogResponse)
async def submit_appeal(
    appeal_data: AppealSubmissionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Submit an appeal for an offense"""
    try:
        reports_service = ReportsService(db)
        offense_log = await reports_service.submit_appeal(
            appeal_data=appeal_data,
            user_id=current_user.id
        )
        
        if not offense_log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Offense log not found or not eligible for appeal"
            )
        
        offense_response = OffenseLogResponse.model_validate(offense_log)
        
        # Add user names for display
        if offense_log.user:
            offense_response.user_name = offense_log.user.full_name
        if offense_log.decided_by_user:
            offense_response.decided_by_name = offense_log.decided_by_user.full_name
        
        return offense_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting appeal: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit appeal"
        )


@router.post("/appeals/decide", response_model=OffenseLogResponse)
async def decide_appeal(
    appeal_data: AppealDecisionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Decide on an appeal (Admin only)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )
    
    try:
        reports_service = ReportsService(db)
        offense_log = await reports_service.decide_appeal(
            appeal_data=appeal_data,
            decided_by=current_user.id
        )
        
        if not offense_log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appeal not found"
            )
        
        offense_response = OffenseLogResponse.model_validate(offense_log)
        
        # Add user names for display
        if offense_log.user:
            offense_response.user_name = offense_log.user.full_name
        if offense_log.decided_by_user:
            offense_response.decided_by_name = offense_log.decided_by_user.full_name
        if offense_log.appeal_decided_by_user:
            offense_response.appeal_decided_by_name = offense_log.appeal_decided_by_user.full_name
        
        return offense_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deciding appeal: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decide appeal"
        )


# User Safety Management Endpoints
@router.get("/safety-status/{user_id}", response_model=UserSafetyStatusResponse)
async def get_user_safety_status(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get user safety status (Admin only or own status)"""
    if not current_user.is_admin and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Can only view own safety status."
        )
    
    try:
        reports_service = ReportsService(db)
        safety_status = await reports_service.get_user_safety_status(user_id)
        
        if not safety_status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User safety status not found"
            )
        
        safety_response = UserSafetyStatusResponse.model_validate(safety_status)
        
        # Add user info for display
        if safety_status.user:
            safety_response.user_name = safety_status.user.full_name
            safety_response.user_email = safety_status.user.email
        
        return safety_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user safety status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user safety status"
        )


@router.put("/safety-status/{user_id}", response_model=UserSafetyStatusResponse)
async def update_user_safety_status(
    user_id: str,
    update_data: UserSafetyUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update user safety status (Admin only)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )
    
    try:
        reports_service = ReportsService(db)
        safety_status = await reports_service.update_user_safety_status(
            user_id=user_id,
            update_data=update_data
        )
        
        safety_response = UserSafetyStatusResponse.model_validate(safety_status)
        
        # Add user info for display
        if safety_status.user:
            safety_response.user_name = safety_status.user.full_name
            safety_response.user_email = safety_status.user.email
        
        return safety_response
        
    except Exception as e:
        logger.error(f"Error updating user safety status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user safety status"
        )
