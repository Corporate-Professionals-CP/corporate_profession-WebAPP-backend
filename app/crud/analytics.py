"""
Analytics CRUD operations
"""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc, case, extract, distinct, text
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.expression import literal_column
from collections import defaultdict

from app.models.analytics import (
    UserAnalytics, ContentAnalytics, PlatformAnalytics, 
    AnalyticsEvent, CohortAnalytics, AnalyticsEventType
)
from app.models.user import User
from app.models.post import Post
from app.models.connection import Connection, ConnectionStatus
from app.models.post_comment import PostComment
from app.models.post_reaction import PostReaction
from app.schemas.analytics import TimeRange, AnalyticsFilterRequest, MetricTrend
from app.schemas.enums import Industry, PostType

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for analytics operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def track_event(
        self,
        event_type: AnalyticsEventType,
        user_id: Optional[str] = None,
        properties: Dict[str, Any] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> None:
        """Track an analytics event"""
        event = AnalyticsEvent(
            user_id=user_id,
            event_type=event_type,
            properties=properties or {},
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id
        )
        
        self.db.add(event)
        await self.db.commit()
        logger.info(f"Tracked event: {event_type} for user: {user_id}")
    
    async def get_user_metrics(
        self,
        filters: AnalyticsFilterRequest
    ) -> Dict[str, Any]:
        """Get user metrics"""
        start_date, end_date = self._get_date_range(filters)
        
        # Total users
        total_users_query = select(func.count(User.id))
        total_users = await self.db.scalar(total_users_query)
        
        # New signups in period
        new_signups_query = select(func.count(User.id)).where(
            and_(
                User.created_at >= start_date,
                User.created_at <= end_date
            )
        )
        new_signups = await self.db.scalar(new_signups_query)
        
        # Daily active users (users who have been active in the last day)
        # Since we don't have login tracking yet, we'll use users who created content recently
        yesterday = datetime.utcnow() - timedelta(days=1)
        dau_query = select(func.count(func.distinct(User.id))).where(
            and_(
                User.is_active == True,
                or_(
                    User.last_login_at >= yesterday,
                    # Include users who created posts/comments recently as "active"
                    User.id.in_(
                        select(Post.user_id).where(Post.created_at >= yesterday)
                    ),
                    User.id.in_(
                        select(PostComment.user_id).where(PostComment.created_at >= yesterday)
                    )
                )
            )
        )
        dau = await self.db.scalar(dau_query)
        
        # Weekly active users
        week_ago = datetime.utcnow() - timedelta(days=7)
        wau_query = select(func.count(func.distinct(User.id))).where(
            and_(
                User.is_active == True,
                or_(
                    User.last_login_at >= week_ago,
                    User.id.in_(
                        select(Post.user_id).where(Post.created_at >= week_ago)
                    ),
                    User.id.in_(
                        select(PostComment.user_id).where(PostComment.created_at >= week_ago)
                    )
                )
            )
        )
        wau = await self.db.scalar(wau_query)
        
        # Monthly active users
        month_ago = datetime.utcnow() - timedelta(days=30)
        mau_query = select(func.count(func.distinct(User.id))).where(
            and_(
                User.is_active == True,
                or_(
                    User.last_login_at >= month_ago,
                    User.id.in_(
                        select(Post.user_id).where(Post.created_at >= month_ago)
                    ),
                    User.id.in_(
                        select(PostComment.user_id).where(PostComment.created_at >= month_ago)
                    )
                )
            )
        )
        mau = await self.db.scalar(mau_query)
        
        # Signup trend
        signup_trend = await self._get_signup_trend(start_date, end_date)
        
        # DAU trend
        dau_trend = await self._get_dau_trend(start_date, end_date)
        
        # Top users
        most_connected_users = await self._get_most_connected_users()
        most_active_posters = await self._get_most_active_posters()
        
        # Signup sources
        signup_sources = await self._get_signup_sources(start_date, end_date)
        
        # Most engaged users
        most_engaged_users = await self._get_most_engaged_users(start_date, end_date)
        
        # Login frequency
        login_frequency = await self._get_login_frequency(start_date, end_date)
        
        return {
            "total_users": total_users or 0,
            "new_signups": new_signups or 0,
            "daily_active_users": dau or 0,
            "weekly_active_users": wau or 0,
            "monthly_active_users": mau or 0,
            "signup_trend": signup_trend,
            "dau_trend": dau_trend,
            "most_connected_users": most_connected_users,
            "most_active_posters": most_active_posters,
            "signup_sources": signup_sources,
            "most_engaged_users": most_engaged_users,
            "login_frequency": login_frequency
        }
    
    async def get_engagement_metrics(
        self,
        filters: AnalyticsFilterRequest
    ) -> Dict[str, Any]:
        """Get engagement metrics"""
        start_date, end_date = self._get_date_range(filters)
        
        # Total engagement counts
        total_posts = await self.db.scalar(
            select(func.count(Post.id)).where(
                and_(
                    Post.created_at >= start_date,
                    Post.created_at <= end_date,
                    Post.deleted == False
                )
            )
        )
        
        total_comments = await self.db.scalar(
            select(func.count(PostComment.id)).where(
                and_(
                    PostComment.created_at >= start_date,
                    PostComment.created_at <= end_date
                )
            )
        )
        
        total_likes = await self.db.scalar(
            select(func.count(PostReaction.user_id)).where(
                and_(
                    PostReaction.created_at >= start_date,
                    PostReaction.created_at <= end_date
                )
            )
        )
        
        total_connections = await self.db.scalar(
            select(func.count(Connection.id)).where(
                and_(
                    Connection.created_at >= start_date,
                    Connection.created_at <= end_date
                )
            )
        )
        
        # Engagement trends
        posts_trend = await self._get_posts_trend(start_date, end_date)
        comments_trend = await self._get_comments_trend(start_date, end_date)
        likes_trend = await self._get_likes_trend(start_date, end_date)
        
        # Session metrics
        avg_session_duration = await self._get_avg_session_duration(start_date, end_date)
        session_duration_distribution = await self._get_session_duration_distribution(start_date, end_date)
        
        return {
            "total_posts": total_posts or 0,
            "total_comments": total_comments or 0,
            "total_likes": total_likes or 0,
            "total_messages": 0,  # Placeholder since we don't have messaging feature
            "total_connections": total_connections or 0,
            "posts_trend": posts_trend,
            "comments_trend": comments_trend,
            "likes_trend": likes_trend,
            "average_session_duration": avg_session_duration or 0.0,
            "repeat_visit_rates": await self._get_repeat_visit_rates(),
            "avg_time_per_session": avg_session_duration or 0.0,
            "session_duration_distribution": session_duration_distribution
        }
    
    async def get_content_analytics(
        self,
        filters: AnalyticsFilterRequest
    ) -> Dict[str, Any]:
        """Get content analytics"""
        start_date, end_date = self._get_date_range(filters)
        
        # Post type distribution
        post_type_dist = await self._get_post_type_distribution(start_date, end_date)
        
        # Most viral posts
        most_viral_posts = await self._get_most_viral_posts(start_date, end_date)
        
        # Most commented posts
        most_commented_posts = await self._get_most_commented_posts(start_date, end_date)
        
        # Average engagement rate
        avg_engagement_rate = await self._get_average_engagement_rate(start_date, end_date)
        
        return {
            "post_type_distribution": post_type_dist,
            "most_viral_posts": most_viral_posts,
            "most_commented_posts": most_commented_posts,
            "most_shared_posts": [],  # Placeholder - we don't have sharing feature yet
            "average_engagement_rate": avg_engagement_rate or 0.0,
            "average_virality_score": 0.0,  # Placeholder
            "career_advice_posts": post_type_dist.get(PostType.DISCUSSION.value, 0),  # Using Discussion as closest to career advice
            "job_posts": post_type_dist.get(PostType.JOB_POSTING.value, 0),
            "company_updates": post_type_dist.get(PostType.PROFESSIONAL_UPDATE.value, 0),
            "engagement_by_post_type": await self._get_engagement_by_post_type(start_date, end_date)
        }
    
    async def get_activation_metrics(
        self,
        filters: AnalyticsFilterRequest
    ) -> Dict[str, Any]:
        """Get user activation metrics"""
        start_date, end_date = self._get_date_range(filters)
        
        # Users who signed up in the period
        users_in_period = await self.db.execute(
            select(User).where(
                and_(
                    User.created_at >= start_date,
                    User.created_at <= end_date
                )
            )
        )
        users = users_in_period.scalars().all()
        
        if not users:
            return {
                "profile_completion_rate": 0.0,
                "profile_picture_upload_rate": 0.0,
                "connection_request_rate": 0.0,
                "activation_funnel": {},
                "avg_time_to_profile_completion": 0.0,
                "avg_time_to_first_connection": 0.0
            }
        
        total_users = len(users)
        
        # Profile completion rate
        completed_profiles = sum(1 for user in users if user.profile_completion >= 80)
        profile_completion_rate = (completed_profiles / total_users) * 100
        
        # Profile picture upload rate
        has_profile_pic = sum(1 for user in users if user.profile_image_url)
        profile_picture_rate = (has_profile_pic / total_users) * 100
        
        # Connection request rate (users who sent at least one connection request)
        connection_senders_count = await self.db.scalar(
            select(func.count(func.distinct(Connection.sender_id))).where(
                and_(
                    Connection.sender_id.in_([user.id for user in users]),
                    Connection.created_at >= start_date
                )
            )
        )
        connection_request_rate = ((connection_senders_count or 0) / total_users) * 100
        
        return {
            "profile_completion_rate": profile_completion_rate,
            "profile_picture_upload_rate": profile_picture_rate,
            "connection_request_rate": connection_request_rate,
            "activation_funnel": await self._get_activation_funnel(users),
            "avg_time_to_profile_completion": await self._get_avg_time_to_activation(users, "profile"),
            "avg_time_to_first_connection": await self._get_avg_time_to_activation(users, "connection"),
            "avg_time_to_first_post": await self._get_avg_time_to_activation(users, "post"),
            "activation_by_industry": await self._get_activation_by_industry(users),
            "activation_by_signup_source": await self._get_activation_by_signup_source(users)
        }
    
    async def get_job_posting_metrics(
        self,
        filters: AnalyticsFilterRequest
    ) -> Dict[str, Any]:
        """Get job posting metrics and analytics"""
        start_date, end_date = self._get_date_range(filters)
        
        # Total job postings in the period
        total_job_postings = await self.db.scalar(
            select(func.count(Post.id)).where(
                and_(
                    Post.post_type == PostType.JOB_POSTING.value,
                    Post.created_at >= start_date,
                    Post.created_at <= end_date,
                    Post.deleted == False
                )
            )
        )
        
        # Active job postings (not expired)
        active_job_postings = await self.db.scalar(
            select(func.count(Post.id)).where(
                and_(
                    Post.post_type == PostType.JOB_POSTING.value,
                    Post.created_at >= start_date,
                    Post.created_at <= end_date,
                    Post.deleted == False,
                    or_(
                        Post.expires_at > datetime.utcnow(),
                        Post.expires_at == None
                    )
                )
            )
        )
        
        # Job posting trends over time
        job_posting_trends = await self._get_job_posting_trends(start_date, end_date)
        
        # Top job categories/industries
        top_job_categories = await self._get_top_job_industries(start_date, end_date)
        
        return {
            "total_job_postings": total_job_postings or 0,
            "active_job_postings": active_job_postings or 0,
            "average_applications_per_job": 0,  # Placeholder for future implementation
            "top_job_categories": top_job_categories,
            "job_posting_trends": job_posting_trends,
            "application_conversion_rate": 0.0,  # Placeholder for future implementation
            "time_to_fill": 0  # Placeholder for future implementation
        }
        
    async def get_cohort_analysis(
        self,
        filters: AnalyticsFilterRequest
    ) -> Dict[str, Any]:
        """Get cohort analysis data"""
        # Get cohort data from database
        cohort_data = await self.db.execute(
            select(CohortAnalytics).order_by(
                CohortAnalytics.cohort_month.desc(),
                CohortAnalytics.period_number.asc()
            )
        )
        
        cohorts = cohort_data.scalars().all()
        
        # Process cohort data
        cohort_dict = defaultdict(list)
        for cohort in cohorts:
            cohort_dict[cohort.cohort_month].append({
                "period": cohort.period_number,
                "retention_rate": cohort.retention_rate,
                "active_users": cohort.active_users,
                "users_in_cohort": cohort.users_in_cohort
            })
        
        # Calculate average retention rate
        if cohorts:
            avg_retention = sum(c.retention_rate for c in cohorts) / len(cohorts)
        else:
            avg_retention = 0.0
        
        # Convert cohort_dict to list format as expected by schema
        cohort_data_list = []
        for cohort_month, periods in cohort_dict.items():
            cohort_data_list.append({
                "cohort_month": str(cohort_month),
                "periods": periods
            })
        
        # Find best and worst performing cohorts
        best_cohort = {"cohort_month": "N/A", "avg_retention": 0.0}
        worst_cohort = {"cohort_month": "N/A", "avg_retention": 100.0}
        
        for cohort_month, periods in cohort_dict.items():
            if periods:
                avg_cohort_retention = sum(p["retention_rate"] for p in periods) / len(periods)
                if avg_cohort_retention > best_cohort["avg_retention"]:
                    best_cohort = {"cohort_month": str(cohort_month), "avg_retention": avg_cohort_retention}
                if avg_cohort_retention < worst_cohort["avg_retention"]:
                    worst_cohort = {"cohort_month": str(cohort_month), "avg_retention": avg_cohort_retention}
        
        # Generate cohort insights
        cohort_insights = []
        if cohorts:
            cohort_insights.append(f"Analyzed {len(set(c.cohort_month for c in cohorts))} cohorts")
            cohort_insights.append(f"Average retention rate: {avg_retention:.1f}%")
            if best_cohort["cohort_month"] != "N/A":
                cohort_insights.append(f"Best performing cohort: {best_cohort['cohort_month']} ({best_cohort['avg_retention']:.1f}%)")
        else:
            cohort_insights.append("No cohort data available")
        
        return {
            "cohort_data": cohort_data_list,
            "retention_rates": {str(k): [p["retention_rate"] for p in v] for k, v in cohort_dict.items()},
            "average_retention_rate": avg_retention,
            "best_performing_cohort": best_cohort,
            "worst_performing_cohort": worst_cohort if worst_cohort["avg_retention"] < 100.0 else {"cohort_month": "N/A", "avg_retention": 0.0},
            "cohort_insights": cohort_insights
        }
    
    def _get_date_range(self, filters: AnalyticsFilterRequest) -> Tuple[datetime, datetime]:
        """Get date range from filters"""
        if filters.time_range == TimeRange.CUSTOM:
            if filters.start_date and filters.end_date:
                return (
                    datetime.combine(filters.start_date, datetime.min.time()),
                    datetime.combine(filters.end_date, datetime.max.time())
                )
        
        end_date = datetime.utcnow()
        
        if filters.time_range == TimeRange.LAST_7_DAYS:
            start_date = end_date - timedelta(days=7)
        elif filters.time_range == TimeRange.LAST_30_DAYS:
            start_date = end_date - timedelta(days=30)
        elif filters.time_range == TimeRange.LAST_90_DAYS:
            start_date = end_date - timedelta(days=90)
        elif filters.time_range == TimeRange.LAST_6_MONTHS:
            start_date = end_date - timedelta(days=180)
        elif filters.time_range == TimeRange.LAST_YEAR:
            start_date = end_date - timedelta(days=365)
        else:
            start_date = end_date - timedelta(days=30)  # Default to 30 days
        
        return start_date, end_date
        
    async def _get_job_posting_trends(self, start_date: datetime, end_date: datetime) -> Dict[str, List[int]]:
        """Get job posting trends over the specified time period"""
        # Calculate the number of days in the period
        days_in_period = (end_date - start_date).days + 1
        
        # Determine the appropriate interval based on the period length
        if days_in_period <= 7:
            # Daily for short periods
            interval = 'day'
            format_str = '%Y-%m-%d'
            delta = timedelta(days=1)
        elif days_in_period <= 31:
            # Weekly for medium periods
            interval = 'week'
            format_str = '%Y-%U'
            delta = timedelta(weeks=1)
        else:
            # Monthly for longer periods
            interval = 'month'
            format_str = '%Y-%m'
            delta = timedelta(days=30)
        
        # Query to get job postings grouped by the interval
        if interval == 'day':
            date_trunc_expr = func.date_trunc('day', Post.created_at)
        elif interval == 'week':
            date_trunc_expr = func.date_trunc('week', Post.created_at)
        else:  # month
            date_trunc_expr = func.date_trunc('month', Post.created_at)
        
        query = select(
            date_trunc_expr.label('interval_date'),
            func.count(Post.id).label('count')
        ).where(
            and_(
                Post.post_type == PostType.JOB_POSTING.value,
                Post.created_at >= start_date,
                Post.created_at <= end_date,
                Post.deleted == False
            )
        ).group_by('interval_date').order_by('interval_date')
        
        result = await self.db.execute(query)
        job_counts_by_interval = {row.interval_date.strftime(format_str): row.count for row in result.all()}
        
        # Create a complete series with zeros for missing intervals
        trends = []
        labels = []
        current_date = start_date
        
        while current_date <= end_date:
            interval_key = current_date.strftime(format_str)
            labels.append(interval_key)
            trends.append(job_counts_by_interval.get(interval_key, 0))
            
            if interval == 'day':
                current_date += timedelta(days=1)
            elif interval == 'week':
                current_date += timedelta(weeks=1)
            else:  # month
                # Move to the first day of the next month
                if current_date.month == 12:
                    current_date = datetime(current_date.year + 1, 1, 1)
                else:
                    current_date = datetime(current_date.year, current_date.month + 1, 1)
        
        return {
            "labels": labels,
            "data": trends
        }
    
    async def _get_top_job_industries(self, start_date: datetime, end_date: datetime, limit: int = 5) -> List[Dict[str, Any]]:
        """Get top industries for job postings"""
        query = select(
            Post.industry,
            func.count(Post.id).label('count')
        ).where(
            and_(
                Post.post_type == PostType.JOB_POSTING.value,
                Post.created_at >= start_date,
                Post.created_at <= end_date,
                Post.deleted == False,
                Post.industry != None
            )
        ).group_by(Post.industry).order_by(desc('count')).limit(limit)
        
        result = await self.db.execute(query)
        top_industries = []
        
        for row in result.all():
            if row.industry:  # Ensure industry is not None
                top_industries.append({
                    "industry": row.industry,
                    "count": row.count
                })
        
        return top_industries
    
    async def _get_signup_trend(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get signup trend data"""
        query = select(
            func.date(User.created_at).label('date'),
            func.count(User.id).label('signups')
        ).where(
            and_(
                User.created_at >= start_date,
                User.created_at <= end_date
            )
        ).group_by(func.date(User.created_at)).order_by(func.date(User.created_at))
        
        result = await self.db.execute(query)
        return [{"date": row.date, "value": row.signups} for row in result.all()]
    
    async def _get_dau_trend(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get DAU trend data"""
        # Since we don't have UserAnalytics data, we'll create a trend based on user activity
        # For now, return a simple trend based on new signups as a proxy
        query = select(
            func.date(User.created_at).label('date'),
            func.count(User.id).label('dau')
        ).where(
            and_(
                User.created_at >= start_date,
                User.created_at <= end_date
            )
        ).group_by(func.date(User.created_at)).order_by(func.date(User.created_at))
        
        result = await self.db.execute(query)
        return [{"date": row.date, "value": row.dau} for row in result.all()]
    
    async def _get_most_connected_users(self) -> List[Dict]:
        """Get users with most connections"""
        query = select(
            User.id,
            User.full_name,
            func.count(Connection.id).label('connection_count')
        ).join(
            Connection, User.id == Connection.sender_id
        ).group_by(User.id, User.full_name).order_by(
            desc('connection_count')
        ).limit(10)
        
        result = await self.db.execute(query)
        return [
            {
                "user_id": row.id,
                "full_name": row.full_name,
                "connection_count": row.connection_count
            }
            for row in result.all()
        ]
    
    async def _get_most_active_posters(self) -> List[Dict]:
        """Get users with most posts"""
        query = select(
            User.id,
            User.full_name,
            func.count(Post.id).label('post_count')
        ).join(
            Post, User.id == Post.user_id
        ).where(
            Post.deleted == False
        ).group_by(User.id, User.full_name).order_by(
            desc('post_count')
        ).limit(10)
        
        result = await self.db.execute(query)
        return [
            {
                "user_id": row.id,
                "full_name": row.full_name,
                "post_count": row.post_count
            }
            for row in result.all()
        ]
    
    async def _get_signup_sources(self, start_date: datetime, end_date: datetime) -> Dict[str, int]:
        """Get signup sources distribution"""
        query = select(
            User.signup_source,
            func.count(User.id).label('count')
        ).where(
            and_(
                User.created_at >= start_date,
                User.created_at <= end_date
            )
        ).group_by(User.signup_source)
        
        result = await self.db.execute(query)
        return {row.signup_source or "direct": row.count for row in result.all()}
    
    # Additional helper methods would continue here...
    # (Implementation truncated for brevity, but would include all the other helper methods)
    
    async def _get_posts_trend(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get posts trend"""
        query = select(
            func.date(Post.created_at).label('date'),
            func.count(Post.id).label('posts')
        ).where(
            and_(
                Post.created_at >= start_date,
                Post.created_at <= end_date,
                Post.deleted == False
            )
        ).group_by(func.date(Post.created_at)).order_by(func.date(Post.created_at))
        
        result = await self.db.execute(query)
        return [{"date": row.date, "value": row.posts} for row in result.all()]
    
    async def _get_comments_trend(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get comments trend"""
        query = select(
            func.date(PostComment.created_at).label('date'),
            func.count(PostComment.id).label('comments')
        ).where(
            and_(
                PostComment.created_at >= start_date,
                PostComment.created_at <= end_date
            )
        ).group_by(func.date(PostComment.created_at)).order_by(func.date(PostComment.created_at))
        
        result = await self.db.execute(query)
        return [{"date": row.date, "value": row.comments} for row in result.all()]
    
    async def _get_likes_trend(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get likes trend"""
        query = select(
            func.date(PostReaction.created_at).label('date'),
            func.count(PostReaction.user_id).label('likes')
        ).where(
            and_(
                PostReaction.created_at >= start_date,
                PostReaction.created_at <= end_date
            )
        ).group_by(func.date(PostReaction.created_at)).order_by(func.date(PostReaction.created_at))
        
        result = await self.db.execute(query)
        return [{"date": row.date, "value": row.likes} for row in result.all()]
    
    async def _get_avg_session_duration(self, start_date: datetime, end_date: datetime) -> float:
        """Get average session duration from session events"""
        try:
            # Get all session start and end events in the time period
            session_events = await self.db.execute(
                select(
                    AnalyticsEvent.user_id,
                    AnalyticsEvent.event_type,
                    AnalyticsEvent.timestamp,
                    AnalyticsEvent.session_id
                ).where(
                    and_(
                        AnalyticsEvent.event_type.in_([
                            AnalyticsEventType.SESSION_START,
                            AnalyticsEventType.SESSION_END
                        ]),
                        AnalyticsEvent.timestamp >= start_date,
                        AnalyticsEvent.timestamp <= end_date,
                        AnalyticsEvent.session_id.isnot(None)
                    )
                ).order_by(AnalyticsEvent.user_id, AnalyticsEvent.timestamp)
            )
            
            events = session_events.all()
            if not events:
                return 0.0
            
            # Group events by session_id and calculate durations
            session_durations = []
            sessions = {}
            
            for event in events:
                session_id = event.session_id
                if session_id not in sessions:
                    sessions[session_id] = {'start': None, 'end': None}
                
                if event.event_type == AnalyticsEventType.SESSION_START:
                    sessions[session_id]['start'] = event.timestamp
                elif event.event_type == AnalyticsEventType.SESSION_END:
                    sessions[session_id]['end'] = event.timestamp
            
            # Calculate durations for complete sessions
            for session_data in sessions.values():
                if session_data['start'] and session_data['end']:
                    duration_minutes = (session_data['end'] - session_data['start']).total_seconds() / 60
                    if duration_minutes > 0:  # Only count positive durations
                        session_durations.append(duration_minutes)
            
            if not session_durations:
                return 0.0
            
            return sum(session_durations) / len(session_durations)
            
        except Exception as e:
            logger.error(f"Error calculating average session duration: {str(e)}")
            return 0.0
    
    async def _get_repeat_visit_rates(self) -> Dict[str, float]:
        """Get repeat visit rates based on session data"""
        try:
            now = datetime.utcnow()
            
            # Calculate repeat visit rates for different time periods
            rates = {}
            
            # Daily repeat visit rate (users who had sessions on multiple days in last 7 days)
            daily_start = now - timedelta(days=7)
            daily_users = await self.db.execute(
                select(
                    AnalyticsEvent.user_id,
                    func.count(func.distinct(func.date(AnalyticsEvent.timestamp))).label('unique_days')
                ).where(
                    and_(
                        AnalyticsEvent.event_type == AnalyticsEventType.SESSION_START,
                        AnalyticsEvent.timestamp >= daily_start,
                        AnalyticsEvent.user_id.isnot(None)
                    )
                ).group_by(AnalyticsEvent.user_id)
            )
            
            daily_results = daily_users.all()
            total_daily_users = len(daily_results)
            repeat_daily_users = sum(1 for user in daily_results if user.unique_days > 1)
            rates["daily"] = (repeat_daily_users / total_daily_users * 100) if total_daily_users > 0 else 0.0
            
            # Weekly repeat visit rate (users who had sessions on multiple weeks in last 4 weeks)
            weekly_start = now - timedelta(weeks=4)
            weekly_users = await self.db.execute(
                select(
                    AnalyticsEvent.user_id,
                    func.count(func.distinct(func.extract('week', AnalyticsEvent.timestamp))).label('unique_weeks')
                ).where(
                    and_(
                        AnalyticsEvent.event_type == AnalyticsEventType.SESSION_START,
                        AnalyticsEvent.timestamp >= weekly_start,
                        AnalyticsEvent.user_id.isnot(None)
                    )
                ).group_by(AnalyticsEvent.user_id)
            )
            
            weekly_results = weekly_users.all()
            total_weekly_users = len(weekly_results)
            repeat_weekly_users = sum(1 for user in weekly_results if user.unique_weeks > 1)
            rates["weekly"] = (repeat_weekly_users / total_weekly_users * 100) if total_weekly_users > 0 else 0.0
            
            # Monthly repeat visit rate (users who had sessions on multiple months in last 6 months)
            monthly_start = now - timedelta(days=180)
            monthly_users = await self.db.execute(
                select(
                    AnalyticsEvent.user_id,
                    func.count(func.distinct(func.extract('month', AnalyticsEvent.timestamp))).label('unique_months')
                ).where(
                    and_(
                        AnalyticsEvent.event_type == AnalyticsEventType.SESSION_START,
                        AnalyticsEvent.timestamp >= monthly_start,
                        AnalyticsEvent.user_id.isnot(None)
                    )
                ).group_by(AnalyticsEvent.user_id)
            )
            
            monthly_results = monthly_users.all()
            total_monthly_users = len(monthly_results)
            repeat_monthly_users = sum(1 for user in monthly_results if user.unique_months > 1)
            rates["monthly"] = (repeat_monthly_users / total_monthly_users * 100) if total_monthly_users > 0 else 0.0
            
            return rates
            
        except Exception as e:
            logger.error(f"Error calculating repeat visit rates: {str(e)}")
            return {
                "daily": 0.0,
                "weekly": 0.0,
                "monthly": 0.0
            }
    
    async def _get_post_type_distribution(self, start_date: datetime, end_date: datetime) -> Dict[str, int]:
        """Get post type distribution"""
        # Initialize distribution for all post types
        distribution = {}
        for post_type in PostType:
            distribution[post_type.value] = 0
        
        # Get actual counts from database
        query = select(
            Post.post_type,
            func.count(Post.id).label('count')
        ).where(
            and_(
                Post.created_at >= start_date,
                Post.created_at <= end_date,
                Post.deleted == False
            )
        ).group_by(Post.post_type)
        
        result = await self.db.execute(query)
        for row in result.all():
            post_type = row.post_type
            # Ensure the post type is valid, otherwise categorize as "Other"
            if post_type in [pt.value for pt in PostType]:
                distribution[post_type] = row.count
            else:
                distribution[PostType.OTHER.value] += row.count
        
        # Only return post types that have posts
        return {k: v for k, v in distribution.items() if v > 0}
    
    async def _get_most_viral_posts(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get most viral posts"""
        # This would implement logic to find posts with highest engagement
        # For now, return placeholder
        return []
    
    async def _get_most_commented_posts(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get most commented posts"""
        query = select(
            Post.id,
            Post.title,
            Post.content,
            func.count(PostComment.id).label('comment_count')
        ).join(
            PostComment, Post.id == PostComment.post_id
        ).where(
            and_(
                Post.created_at >= start_date,
                Post.created_at <= end_date,
                Post.deleted == False
            )
        ).group_by(Post.id, Post.title, Post.content).order_by(
            desc('comment_count')
        ).limit(10)
        
        result = await self.db.execute(query)
        return [
            {
                "post_id": row.id,
                "title": row.title,
                "content": row.content[:100] + "..." if len(row.content) > 100 else row.content,
                "comment_count": row.comment_count
            }
            for row in result.all()
        ]
    
    async def _get_average_engagement_rate(self, start_date: datetime, end_date: datetime) -> float:
        """Get average engagement rate"""
        # This would implement logic to calculate engagement rate
        # For now, return placeholder
        return 0.0
    
    async def _get_engagement_by_post_type(self, start_date: datetime, end_date: datetime) -> Dict[str, Dict[str, float]]:
        """Get engagement metrics by post type"""
        engagement_by_type = {}
        
        # Initialize engagement stats for all post types
        for post_type in PostType:
            engagement_by_type[post_type.value] = {
                "total_posts": 0,
                "total_comments": 0,
                "total_likes": 0,
                "avg_engagement_rate": 0.0
            }
        
        # Get engagement data for each post type
        for post_type in PostType:
            # Count posts of this type
            posts_count = await self.db.scalar(
                select(func.count(Post.id)).where(
                    and_(
                        Post.post_type == post_type.value,
                        Post.created_at >= start_date,
                        Post.created_at <= end_date,
                        Post.deleted == False
                    )
                )
            )
            
            # Count comments on posts of this type
            comments_count = await self.db.scalar(
                select(func.count(PostComment.id)).join(
                    Post, PostComment.post_id == Post.id
                ).where(
                    and_(
                        Post.post_type == post_type.value,
                        Post.created_at >= start_date,
                        Post.created_at <= end_date,
                        Post.deleted == False
                    )
                )
            )
            
            # Count likes on posts of this type
            likes_count = await self.db.scalar(
                select(func.count(PostReaction.user_id)).join(
                    Post, PostReaction.post_id == Post.id
                ).where(
                    and_(
                        Post.post_type == post_type.value,
                        Post.created_at >= start_date,
                        Post.created_at <= end_date,
                        Post.deleted == False
                    )
                )
            )
            
            # Calculate engagement rate
            total_engagements = (comments_count or 0) + (likes_count or 0)
            engagement_rate = (total_engagements / posts_count) if posts_count > 0 else 0.0
            
            engagement_by_type[post_type.value] = {
                "total_posts": posts_count or 0,
                "total_comments": comments_count or 0,
                "total_likes": likes_count or 0,
                "avg_engagement_rate": engagement_rate
            }
        
        # Only return post types that have posts
        return {k: v for k, v in engagement_by_type.items() if v["total_posts"] > 0}
    
    async def _get_activation_funnel(self, users: List[User]) -> Dict[str, Dict[str, Any]]:
        """Get activation funnel data"""
        # This would implement logic to calculate activation funnel
        # For now, return placeholder
        return {}
    
    async def _get_avg_time_to_activation(self, users: List[User], activation_type: str) -> float:
        """Get average time to activation"""
        # This would implement logic to calculate time to activation
        # For now, return placeholder
        return 0.0

    async def _get_most_engaged_users(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get most engaged users based on posts, comments, and reactions"""
        # Create a comprehensive engagement score
        query = select(
            User.id,
            User.full_name,
            User.email,
            func.coalesce(func.count(distinct(Post.id)), 0).label('post_count'),
            func.coalesce(func.count(distinct(PostComment.id)), 0).label('comment_count'),
            func.coalesce(func.count(distinct(PostReaction.user_id)), 0).label('reaction_count')
        ).select_from(User).outerjoin(
            Post, and_(Post.user_id == User.id, Post.deleted == False)
        ).outerjoin(
            PostComment, and_(PostComment.user_id == User.id)
        ).outerjoin(
            PostReaction, PostReaction.user_id == User.id
        ).where(
            and_(
                User.created_at >= start_date,
                User.created_at <= end_date,
                User.is_active == True
            )
        ).group_by(User.id, User.full_name, User.email).having(
            func.coalesce(func.count(distinct(Post.id)), 0) +
            func.coalesce(func.count(distinct(PostComment.id)), 0) +
            func.coalesce(func.count(distinct(PostReaction.user_id)), 0) > 0
        ).order_by(
            desc(
                func.coalesce(func.count(distinct(Post.id)), 0) +
                func.coalesce(func.count(distinct(PostComment.id)), 0) +
                func.coalesce(func.count(distinct(PostReaction.user_id)), 0)
            )
        ).limit(10)
        
        result = await self.db.execute(query)
        return [
            {
                "user_id": row.id,
                "full_name": row.full_name,
                "email": row.email,
                "engagement_score": row.post_count + row.comment_count + row.reaction_count,
                "posts": row.post_count,
                "comments": row.comment_count,
                "reactions": row.reaction_count
            }
            for row in result.all()
        ]

    async def _get_login_frequency(self, start_date: datetime, end_date: datetime) -> Dict[str, int]:
        """Get login frequency distribution"""
        # Since we don't have login tracking, we'll use activity as proxy
        # Count users by their posting activity frequency
        query = select(
            User.id,
            func.count(distinct(Post.id)).label('post_count')
        ).select_from(User).outerjoin(
            Post, and_(Post.user_id == User.id, Post.deleted == False)
        ).where(
            and_(
                User.created_at >= start_date,
                User.created_at <= end_date,
                User.is_active == True
            )
        ).group_by(User.id)
        
        result = await self.db.execute(query)
        frequency_counts = {"daily": 0, "weekly": 0, "monthly": 0, "occasional": 0}
        
        for row in result.all():
            # Categorize based on posting frequency
            if row.post_count >= 7:  # More than 7 posts (assuming daily)
                frequency_counts["daily"] += 1
            elif row.post_count >= 3:  # 3-6 posts (weekly)
                frequency_counts["weekly"] += 1
            elif row.post_count >= 1:  # 1-2 posts (monthly)
                frequency_counts["monthly"] += 1
            else:  # No posts (occasional)
                frequency_counts["occasional"] += 1
        
        return frequency_counts

    async def _get_session_duration_distribution(self, start_date: datetime, end_date: datetime) -> Dict[str, int]:
        """Get session duration distribution from actual session events"""
        try:
            # Get all session start and end events in the time period
            session_events = await self.db.execute(
                select(
                    AnalyticsEvent.user_id,
                    AnalyticsEvent.event_type,
                    AnalyticsEvent.timestamp,
                    AnalyticsEvent.session_id
                ).where(
                    and_(
                        AnalyticsEvent.event_type.in_([
                            AnalyticsEventType.SESSION_START,
                            AnalyticsEventType.SESSION_END
                        ]),
                        AnalyticsEvent.timestamp >= start_date,
                        AnalyticsEvent.timestamp <= end_date,
                        AnalyticsEvent.session_id.isnot(None)
                    )
                ).order_by(AnalyticsEvent.user_id, AnalyticsEvent.timestamp)
            )
            
            events = session_events.all()
            if not events:
                # Return empty distribution if no session data
                return {
                    "0-5 min": 0,
                    "5-15 min": 0,
                    "15-30 min": 0,
                    "30-60 min": 0,
                    "60+ min": 0
                }
            
            # Group events by session_id and calculate durations
            sessions = {}
            for event in events:
                session_id = event.session_id
                if session_id not in sessions:
                    sessions[session_id] = {'start': None, 'end': None}
                
                if event.event_type == AnalyticsEventType.SESSION_START:
                    sessions[session_id]['start'] = event.timestamp
                elif event.event_type == AnalyticsEventType.SESSION_END:
                    sessions[session_id]['end'] = event.timestamp
            
            # Calculate durations and categorize
            distribution = {
                "0-5 min": 0,
                "5-15 min": 0,
                "15-30 min": 0,
                "30-60 min": 0,
                "60+ min": 0
            }
            
            for session_data in sessions.values():
                if session_data['start'] and session_data['end']:
                    duration_minutes = (session_data['end'] - session_data['start']).total_seconds() / 60
                    
                    if duration_minutes <= 5:
                        distribution["0-5 min"] += 1
                    elif duration_minutes <= 15:
                        distribution["5-15 min"] += 1
                    elif duration_minutes <= 30:
                        distribution["15-30 min"] += 1
                    elif duration_minutes <= 60:
                        distribution["30-60 min"] += 1
                    else:
                        distribution["60+ min"] += 1
            
            return distribution
            
        except Exception as e:
            logger.error(f"Error calculating session duration distribution: {str(e)}")
            # Return placeholder distribution on error
            return {
                "0-5 min": 0,
                "5-15 min": 0,
                "15-30 min": 0,
                "30-60 min": 0,
                "60+ min": 0
            }

    async def _get_activation_by_industry(self, users: List[User]) -> Dict[str, float]:
        """Get activation rates by industry"""
        # Initialize stats for all industry enum values
        industry_stats = {}
        for industry in Industry:
            industry_stats[industry.value] = {"total": 0, "activated": 0}
        
        # Group users by industry and calculate activation rates
        for user in users:
            # Get the user's industry, defaulting to "Other" if not set or invalid
            user_industry = user.industry if hasattr(user, 'industry') and user.industry else Industry.OTHER.value
            
            # Ensure the industry is valid, default to "Other" if not
            if user_industry not in [ind.value for ind in Industry]:
                user_industry = Industry.OTHER.value
            
            industry_stats[user_industry]["total"] += 1
            if user.profile_completion >= 80:
                industry_stats[user_industry]["activated"] += 1
        
        # Calculate activation rates (only include industries with users)
        activation_rates = {}
        for industry, stats in industry_stats.items():
            if stats["total"] > 0:
                activation_rates[industry] = (stats["activated"] / stats["total"]) * 100
        
        return activation_rates

    async def _get_activation_by_signup_source(self, users: List[User]) -> Dict[str, float]:
        """Get activation rates by signup source"""
        # Group users by signup source and calculate activation rates
        source_stats = {}
        for user in users:
            source = user.signup_source or "direct"
            if source not in source_stats:
                source_stats[source] = {"total": 0, "activated": 0}
            
            source_stats[source]["total"] += 1
            if user.profile_completion >= 80:
                source_stats[source]["activated"] += 1
        
        # Calculate activation rates
        activation_rates = {}
        for source, stats in source_stats.items():
            if stats["total"] > 0:
                activation_rates[source] = (stats["activated"] / stats["total"]) * 100
            else:
                activation_rates[source] = 0.0
        
        return activation_rates
