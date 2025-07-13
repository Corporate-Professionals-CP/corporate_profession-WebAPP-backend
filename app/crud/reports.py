"""
Reports and User Safety CRUD operations
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc, update
from sqlalchemy.orm import selectinload
from collections import defaultdict
import math

from app.models.reports import (
    Report, UserOffenseLog, ReportResolutionMetrics, UserSafetyStatus,
    ReportType, ReportStatus, ReportPriority, ContentType, OffenseType
)
from app.models.user import User
from app.schemas.reports import (
    ReportCreateRequest, ReportUpdateRequest, ReportFilterRequest,
    OffenseLogCreateRequest, AppealSubmissionRequest, AppealDecisionRequest,
    UserSafetyUpdateRequest
)

logger = logging.getLogger(__name__)


class ReportsService:
    """Service for managing reports and user safety"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # Report Management
    async def create_report(
        self, 
        report_data: ReportCreateRequest, 
        reporter_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Report:
        """Create a new report"""
        try:
            # Determine priority based on report type
            priority = self._determine_priority(report_data.report_type)
            
            report = Report(
                reporter_id=reporter_id,
                reported_user_id=report_data.reported_user_id,
                content_type=report_data.content_type,
                content_id=report_data.content_id,
                content_url=report_data.content_url,
                report_type=report_data.report_type,
                title=report_data.title,
                description=report_data.description,
                evidence_urls=report_data.evidence_urls,
                priority=priority,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            self.db.add(report)
            await self.db.commit()
            await self.db.refresh(report)
            
            # Load relationships for the response
            query = select(Report).options(
                selectinload(Report.reporter),
                selectinload(Report.reported_user),
                selectinload(Report.assigned_moderator),
                selectinload(Report.resolver)
            ).where(Report.id == report.id)
            
            result = await self.db.execute(query)
            report_with_relationships = result.scalar_one()
            
            # Update user safety status if reporting a user
            if report_data.reported_user_id:
                await self._update_user_safety_on_report(report_data.reported_user_id, report_data.report_type)
            
            logger.info(f"Created report {report.id} by user {reporter_id}")
            return report_with_relationships
            
        except Exception as e:
            logger.error(f"Error creating report: {str(e)}")
            await self.db.rollback()
            raise
    
    async def get_report(self, report_id: int) -> Optional[Report]:
        """Get a specific report with relationships"""
        query = select(Report).options(
            selectinload(Report.reporter),
            selectinload(Report.reported_user),
            selectinload(Report.assigned_moderator),
            selectinload(Report.resolver)
        ).where(Report.id == report_id)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_reports(
        self, 
        filters: ReportFilterRequest,
        include_relationships: bool = True
    ) -> Tuple[List[Report], int]:
        """Get reports with filtering and pagination"""
        query = select(Report)
        
        if include_relationships:
            query = query.options(
                selectinload(Report.reporter),
                selectinload(Report.reported_user),
                selectinload(Report.assigned_moderator),
                selectinload(Report.resolver)
            )
        
        # Apply filters
        conditions = []
        
        if filters.status:
            conditions.append(Report.status.in_(filters.status))
        
        if filters.report_type:
            conditions.append(Report.report_type.in_(filters.report_type))
        
        if filters.priority:
            conditions.append(Report.priority.in_(filters.priority))
        
        if filters.assigned_to:
            conditions.append(Report.assigned_to == filters.assigned_to)
        
        if filters.reported_user_id:
            conditions.append(Report.reported_user_id == filters.reported_user_id)
        
        if filters.content_type:
            conditions.append(Report.content_type == filters.content_type)
        
        if filters.date_from:
            conditions.append(Report.created_at >= filters.date_from)
        
        if filters.date_to:
            conditions.append(Report.created_at <= filters.date_to)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Count total
        count_query = select(func.count(Report.id))
        if conditions:
            count_query = count_query.where(and_(*conditions))
        
        total = await self.db.scalar(count_query)
        
        # Apply pagination and ordering
        query = query.order_by(desc(Report.created_at))
        query = query.offset((filters.page - 1) * filters.limit).limit(filters.limit)
        
        result = await self.db.execute(query)
        reports = result.scalars().all()
        
        return reports, total or 0
    
    async def update_report(
        self, 
        report_id: int, 
        update_data: ReportUpdateRequest, 
        updated_by: str
    ) -> Optional[Report]:
        """Update a report"""
        try:
            report = await self.get_report(report_id)
            if not report:
                return None
            
            update_dict = update_data.model_dump(exclude_unset=True)
            
            # Handle status changes
            if update_data.status and update_data.status != report.status:
                if update_data.status == ReportStatus.RESOLVED:
                    update_dict['resolved_at'] = datetime.utcnow()
                    update_dict['resolved_by'] = updated_by
                elif update_data.status == ReportStatus.ESCALATED:
                    update_dict['escalated_at'] = datetime.utcnow()
            
            # Handle assignment
            if update_data.assigned_to and update_data.assigned_to != report.assigned_to:
                update_dict['assigned_at'] = datetime.utcnow()
            
            update_dict['updated_at'] = datetime.utcnow()
            
            # Apply updates
            for key, value in update_dict.items():
                setattr(report, key, value)
            
            await self.db.commit()
            await self.db.refresh(report)
            
            logger.info(f"Updated report {report_id} by {updated_by}")
            return report
            
        except Exception as e:
            logger.error(f"Error updating report {report_id}: {str(e)}")
            await self.db.rollback()
            raise
    
    async def assign_report(
        self, 
        report_id: int, 
        assigned_to: str, 
        assigned_by: str
    ) -> Optional[Report]:
        """Assign a report to a moderator"""
        update_data = ReportUpdateRequest(
            assigned_to=assigned_to,
            status=ReportStatus.INVESTIGATING
        )
        return await self.update_report(report_id, update_data, assigned_by)
    
    async def resolve_report(
        self, 
        report_id: int, 
        resolution_notes: str, 
        resolved_by: str
    ) -> Optional[Report]:
        """Resolve a report"""
        update_data = ReportUpdateRequest(
            status=ReportStatus.RESOLVED,
            resolution_notes=resolution_notes
        )
        return await self.update_report(report_id, update_data, resolved_by)
    
    async def escalate_report(
        self, 
        report_id: int, 
        escalated_to: str, 
        escalation_reason: str, 
        escalated_by: str
    ) -> Optional[Report]:
        """Escalate a report"""
        update_data = ReportUpdateRequest(
            status=ReportStatus.ESCALATED,
            escalated_to=escalated_to,
            escalation_reason=escalation_reason
        )
        return await self.update_report(report_id, update_data, escalated_by)
    
    # User Offense Management
    async def create_offense_log(
        self, 
        offense_data: OffenseLogCreateRequest, 
        decided_by: str
    ) -> UserOffenseLog:
        """Create a new offense log entry"""
        try:
            # Calculate expiration time if duration is specified
            expires_at = None
            if offense_data.duration_hours:
                expires_at = datetime.utcnow() + timedelta(hours=offense_data.duration_hours)
            
            offense_log = UserOffenseLog(
                user_id=offense_data.user_id,
                offense_type=offense_data.offense_type,
                offense_description=offense_data.offense_description,
                related_report_id=offense_data.related_report_id,
                action_taken=offense_data.action_taken,
                severity_level=offense_data.severity_level,
                duration_hours=offense_data.duration_hours,
                expires_at=expires_at,
                decided_by=decided_by,
                decision_notes=offense_data.decision_notes
            )
            
            self.db.add(offense_log)
            await self.db.commit()
            await self.db.refresh(offense_log)
            
            # Load relationships for the response
            query = select(UserOffenseLog).options(
                selectinload(UserOffenseLog.user),
                selectinload(UserOffenseLog.decided_by_user),
                selectinload(UserOffenseLog.appeal_decided_by_user),
                selectinload(UserOffenseLog.related_report)
            ).where(UserOffenseLog.id == offense_log.id)
            
            result = await self.db.execute(query)
            offense_log_with_relationships = result.scalar_one()
            
            # Update user safety status
            await self._update_user_safety_on_offense(offense_data.user_id, offense_data.offense_type, offense_data.severity_level)
            
            logger.info(f"Created offense log {offense_log.id} for user {offense_data.user_id}")
            return offense_log_with_relationships
            
        except Exception as e:
            logger.error(f"Error creating offense log: {str(e)}")
            await self.db.rollback()
            raise
    
    async def get_user_offense_logs(
        self, 
        user_id: str, 
        include_inactive: bool = False
    ) -> List[UserOffenseLog]:
        """Get offense logs for a user"""
        query = select(UserOffenseLog).options(
            selectinload(UserOffenseLog.user),
            selectinload(UserOffenseLog.related_report),
            selectinload(UserOffenseLog.decided_by_user),
            selectinload(UserOffenseLog.appeal_decided_by_user)
        ).where(UserOffenseLog.user_id == user_id)
        
        if not include_inactive:
            query = query.where(UserOffenseLog.is_active == True)
        
        query = query.order_by(desc(UserOffenseLog.created_at))
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def submit_appeal(
        self, 
        appeal_data: AppealSubmissionRequest, 
        user_id: str
    ) -> Optional[UserOffenseLog]:
        """Submit an appeal for an offense"""
        try:
            query = select(UserOffenseLog).where(
                and_(
                    UserOffenseLog.id == appeal_data.offense_log_id,
                    UserOffenseLog.user_id == user_id,
                    UserOffenseLog.is_active == True
                )
            )
            
            result = await self.db.execute(query)
            offense_log = result.scalar_one_or_none()
            
            if not offense_log:
                return None
            
            offense_log.appeal_submitted = True
            offense_log.appeal_notes = appeal_data.appeal_notes
            offense_log.is_appealed = True
            offense_log.updated_at = datetime.utcnow()
            
            await self.db.commit()
            await self.db.refresh(offense_log)
            
            logger.info(f"Appeal submitted for offense log {appeal_data.offense_log_id}")
            return offense_log
            
        except Exception as e:
            logger.error(f"Error submitting appeal: {str(e)}")
            await self.db.rollback()
            raise
    
    async def decide_appeal(
        self, 
        appeal_data: AppealDecisionRequest, 
        decided_by: str
    ) -> Optional[UserOffenseLog]:
        """Decide on an appeal"""
        try:
            query = select(UserOffenseLog).where(
                and_(
                    UserOffenseLog.id == appeal_data.offense_log_id,
                    UserOffenseLog.appeal_submitted == True
                )
            )
            
            result = await self.db.execute(query)
            offense_log = result.scalar_one_or_none()
            
            if not offense_log:
                return None
            
            offense_log.appeal_decided_by = decided_by
            offense_log.appeal_decision = appeal_data.appeal_decision
            offense_log.appeal_decided_at = datetime.utcnow()
            offense_log.updated_at = datetime.utcnow()
            
            # If appeal is approved, deactivate the offense
            if appeal_data.appeal_decision == "approved":
                offense_log.is_active = False
                # Update user safety status
                await self._restore_user_safety_on_appeal(offense_log.user_id)
            
            await self.db.commit()
            await self.db.refresh(offense_log)
            
            logger.info(f"Appeal decided for offense log {appeal_data.offense_log_id}: {appeal_data.appeal_decision}")
            return offense_log
            
        except Exception as e:
            logger.error(f"Error deciding appeal: {str(e)}")
            await self.db.rollback()
            raise
    
    # User Safety Management
    async def get_user_safety_status(self, user_id: str) -> Optional[UserSafetyStatus]:
        """Get user safety status"""
        query = select(UserSafetyStatus).where(UserSafetyStatus.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def update_user_safety_status(
        self, 
        user_id: str, 
        update_data: UserSafetyUpdateRequest
    ) -> UserSafetyStatus:
        """Update user safety status"""
        try:
            safety_status = await self.get_user_safety_status(user_id)
            
            if not safety_status:
                # Create new safety status
                safety_status = UserSafetyStatus(user_id=user_id)
                self.db.add(safety_status)
            
            update_dict = update_data.model_dump(exclude_unset=True)
            
            # Handle ban logic
            if update_data.is_banned is True and not safety_status.is_banned:
                update_dict['banned_at'] = datetime.utcnow()
            elif update_data.is_banned is False:
                update_dict['banned_at'] = None
                update_dict['ban_reason'] = None
            
            update_dict['updated_at'] = datetime.utcnow()
            
            # Apply updates
            for key, value in update_dict.items():
                setattr(safety_status, key, value)
            
            await self.db.commit()
            await self.db.refresh(safety_status)
            
            logger.info(f"Updated safety status for user {user_id}")
            return safety_status
            
        except Exception as e:
            logger.error(f"Error updating user safety status: {str(e)}")
            await self.db.rollback()
            raise
    
    # Dashboard and Analytics
    async def get_report_dashboard_data(self) -> Dict:
        """Get dashboard data for reports"""
        try:
            # Current statistics
            total_reports = await self.db.scalar(select(func.count(Report.id)))
            new_reports = await self.db.scalar(
                select(func.count(Report.id)).where(Report.status == ReportStatus.NEW)
            )
            investigating_reports = await self.db.scalar(
                select(func.count(Report.id)).where(Report.status == ReportStatus.INVESTIGATING)
            )
            resolved_reports = await self.db.scalar(
                select(func.count(Report.id)).where(Report.status == ReportStatus.RESOLVED)
            )
            escalated_reports = await self.db.scalar(
                select(func.count(Report.id)).where(Report.status == ReportStatus.ESCALATED)
            )
            
            # Resolution time metrics
            resolved_query = select(
                func.extract('epoch', Report.resolved_at - Report.created_at) / 3600
            ).where(
                and_(
                    Report.status == ReportStatus.RESOLVED,
                    Report.resolved_at.is_not(None)
                )
            )
            
            resolution_times = await self.db.execute(resolved_query)
            resolution_times_list = [float(t[0]) for t in resolution_times.fetchall() if t[0]]
            
            avg_resolution_time = sum(resolution_times_list) / len(resolution_times_list) if resolution_times_list else 0
            under_24h = len([t for t in resolution_times_list if t <= 24])
            under_72h = len([t for t in resolution_times_list if t <= 72])
            
            under_24h_percent = (under_24h / len(resolution_times_list) * 100) if resolution_times_list else 0
            under_72h_percent = (under_72h / len(resolution_times_list) * 100) if resolution_times_list else 0
            
            # Report type breakdown
            type_query = select(
                Report.report_type,
                func.count(Report.id)
            ).group_by(Report.report_type)
            
            type_results = await self.db.execute(type_query)
            report_type_breakdown = {str(row[0]): row[1] for row in type_results.fetchall()}
            
            # Priority breakdown
            priority_query = select(
                Report.priority,
                func.count(Report.id)
            ).group_by(Report.priority)
            
            priority_results = await self.db.execute(priority_query)
            priority_breakdown = {str(row[0]): row[1] for row in priority_results.fetchall()}
            
            # Recent reports
            recent_query = select(Report).options(
                selectinload(Report.reporter),
                selectinload(Report.reported_user)
            ).order_by(desc(Report.created_at)).limit(10)
            
            recent_result = await self.db.execute(recent_query)
            recent_reports = recent_result.scalars().all()
            
            # User safety overview
            total_users = await self.db.scalar(select(func.count(User.id)))
            
            suspended_users = await self.db.scalar(
                select(func.count(UserSafetyStatus.user_id)).where(
                    UserSafetyStatus.is_suspended == True
                )
            ) or 0
            
            banned_users = await self.db.scalar(
                select(func.count(UserSafetyStatus.user_id)).where(
                    UserSafetyStatus.is_banned == True
                )
            ) or 0
            
            return {
                'total_reports': total_reports or 0,
                'new_reports': new_reports or 0,
                'investigating_reports': investigating_reports or 0,
                'resolved_reports': resolved_reports or 0,
                'escalated_reports': escalated_reports or 0,
                'avg_resolution_time_hours': avg_resolution_time,
                'reports_resolved_under_24h_percent': under_24h_percent,
                'reports_resolved_under_72h_percent': under_72h_percent,
                'report_type_breakdown': report_type_breakdown,
                'priority_breakdown': priority_breakdown,
                'recent_reports': recent_reports,
                'total_active_users': total_users or 0,
                'suspended_users': suspended_users,
                'banned_users': banned_users,
                'users_with_restrictions': suspended_users + banned_users,
                'moderator_workload': {},  # TODO: Implement moderator workload calculation
                'daily_report_counts': [],  # TODO: Implement daily trend data
                'resolution_time_trend': [],  # TODO: Implement resolution time trend
                'generated_at': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error getting dashboard data: {str(e)}")
            raise
    
    async def get_report_metrics(self, date_from: datetime, date_to: datetime) -> List[ReportResolutionMetrics]:
        """Get report resolution metrics for a date range"""
        query = select(ReportResolutionMetrics).where(
            and_(
                ReportResolutionMetrics.date >= date_from,
                ReportResolutionMetrics.date <= date_to
            )
        ).order_by(ReportResolutionMetrics.date)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    # Helper methods
    def _determine_priority(self, report_type: ReportType) -> ReportPriority:
        """Determine priority based on report type"""
        high_priority_types = [
            ReportType.VIOLENCE_THREATS,
            ReportType.HARASSMENT,
            ReportType.HATE_SPEECH,
            ReportType.DISCRIMINATION
        ]
        
        medium_priority_types = [
            ReportType.BULLYING,
            ReportType.INAPPROPRIATE_CONTENT,
            ReportType.PRIVACY_VIOLATION,
            ReportType.IMPERSONATION
        ]
        
        if report_type in high_priority_types:
            return ReportPriority.HIGH
        elif report_type in medium_priority_types:
            return ReportPriority.MEDIUM
        else:
            return ReportPriority.LOW
    
    async def _update_user_safety_on_report(self, user_id: str, report_type: ReportType):
        """Update user safety status when they are reported"""
        try:
            safety_status = await self.get_user_safety_status(user_id)
            
            if not safety_status:
                safety_status = UserSafetyStatus(user_id=user_id)
                self.db.add(safety_status)
            
            # Adjust trust score based on report type
            trust_score_impact = {
                ReportType.VIOLENCE_THREATS: -20,
                ReportType.HARASSMENT: -15,
                ReportType.HATE_SPEECH: -15,
                ReportType.DISCRIMINATION: -10,
                ReportType.BULLYING: -10,
                ReportType.INAPPROPRIATE_CONTENT: -5,
                ReportType.SPAM: -5,
                ReportType.FAKE_PROFILE: -10,
                ReportType.IMPERSONATION: -10
            }
            
            impact = trust_score_impact.get(report_type, -3)
            safety_status.trust_score = max(0, safety_status.trust_score + impact)
            
            # Update risk level
            if safety_status.trust_score < 25:
                safety_status.risk_level = "critical"
            elif safety_status.trust_score < 50:
                safety_status.risk_level = "high"
            elif safety_status.trust_score < 75:
                safety_status.risk_level = "medium"
            else:
                safety_status.risk_level = "low"
            
            safety_status.updated_at = datetime.utcnow()
            await self.db.commit()
            
        except Exception as e:
            logger.error(f"Error updating user safety on report: {str(e)}")
    
    async def _update_user_safety_on_offense(self, user_id: str, offense_type: OffenseType, severity_level: int):
        """Update user safety status when an offense is recorded"""
        try:
            safety_status = await self.get_user_safety_status(user_id)
            
            if not safety_status:
                safety_status = UserSafetyStatus(user_id=user_id)
                self.db.add(safety_status)
            
            # Update counts
            if offense_type == OffenseType.WARNING:
                safety_status.warning_count += 1
            else:
                safety_status.strike_count += 1
            
            safety_status.last_offense_at = datetime.utcnow()
            
            # Apply restrictions based on offense type
            if offense_type == OffenseType.TEMPORARY_SUSPENSION:
                safety_status.is_suspended = True
            elif offense_type == OffenseType.PERMANENT_BAN:
                safety_status.is_banned = True
            elif offense_type == OffenseType.CONTENT_REMOVAL:
                pass  # No direct restrictions
            elif offense_type == OffenseType.FEATURE_RESTRICTION:
                # Apply feature restrictions based on severity
                if severity_level >= 4:
                    safety_status.can_post = False
                    safety_status.can_comment = False
                elif severity_level >= 3:
                    safety_status.can_post = False
                elif severity_level >= 2:
                    safety_status.can_comment = False
            
            # Adjust trust score
            trust_score_impact = severity_level * -10
            safety_status.trust_score = max(0, safety_status.trust_score + trust_score_impact)
            
            safety_status.updated_at = datetime.utcnow()
            await self.db.commit()
            
        except Exception as e:
            logger.error(f"Error updating user safety on offense: {str(e)}")
    
    async def _restore_user_safety_on_appeal(self, user_id: str):
        """Restore user safety status when an appeal is approved"""
        try:
            safety_status = await self.get_user_safety_status(user_id)
            
            if safety_status:
                # Restore trust score partially
                safety_status.trust_score = min(100, safety_status.trust_score + 20)
                
                # Reset some restrictions
                safety_status.can_post = True
                safety_status.can_comment = True
                safety_status.can_message = True
                safety_status.can_connect = True
                
                safety_status.updated_at = datetime.utcnow()
                await self.db.commit()
                
        except Exception as e:
            logger.error(f"Error restoring user safety on appeal: {str(e)}")
