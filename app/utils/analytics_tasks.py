"""
Background tasks for analytics data computation
"""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, update
from collections import defaultdict

from app.db.database import get_db
from app.models.analytics import (
    UserAnalytics, PlatformAnalytics, ContentAnalytics, 
    CohortAnalytics, AnalyticsEvent, AnalyticsEventType
)
from app.models.user import User
from app.models.post import Post
from app.models.connection import Connection
from app.models.post_comment import PostComment
from app.models.post_reaction import PostReaction
from app.models.bookmark import Bookmark

logger = logging.getLogger(__name__)


class AnalyticsTasksService:
    """Service for running analytics background tasks"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def compute_daily_user_analytics(self, target_date: date = None) -> None:
        """Compute daily user analytics for all users"""
        if target_date is None:
            target_date = date.today() - timedelta(days=1)  # Process previous day
        
        try:
            logger.info(f"Computing daily user analytics for {target_date}")
            
            # Get all users
            users_query = select(User).where(User.is_active == True)
            users_result = await self.db.execute(users_query)
            users = users_result.scalars().all()
            
            for user in users:
                await self._compute_user_daily_analytics(user, target_date)
            
            await self.db.commit()
            logger.info(f"Completed daily user analytics for {target_date}")
            
        except Exception as e:
            logger.error(f"Error computing daily user analytics: {str(e)}")
            await self.db.rollback()
            raise
    
    async def _compute_user_daily_analytics(self, user: User, target_date: date) -> None:
        """Compute analytics for a single user on a specific date"""
        start_datetime = datetime.combine(target_date, datetime.min.time())
        end_datetime = datetime.combine(target_date, datetime.max.time())
        
        # Check if analytics already exist for this user and date
        existing_analytics = await self.db.scalar(
            select(UserAnalytics).where(
                and_(
                    UserAnalytics.user_id == user.id,
                    UserAnalytics.date == target_date
                )
            )
        )
        
        # Count various activities for the day
        login_count = await self._count_user_events(
            user.id, AnalyticsEventType.USER_LOGIN, start_datetime, end_datetime
        )
        
        posts_created = await self.db.scalar(
            select(func.count(Post.id)).where(
                and_(
                    Post.user_id == user.id,
                    Post.created_at >= start_datetime,
                    Post.created_at <= end_datetime,
                    Post.deleted == False
                )
            )
        ) or 0
        
        comments_made = await self.db.scalar(
            select(func.count(PostComment.id)).where(
                and_(
                    PostComment.user_id == user.id,
                    PostComment.created_at >= start_datetime,
                    PostComment.created_at <= end_datetime
                )
            )
        ) or 0
        
        likes_given = await self.db.scalar(
            select(func.count(PostReaction.post_id)).where(
                and_(
                    PostReaction.user_id == user.id,
                    PostReaction.created_at >= start_datetime,
                    PostReaction.created_at <= end_datetime
                )
            )
        ) or 0
        
        connections_made = await self.db.scalar(
            select(func.count(Connection.id)).where(
                and_(
                    Connection.sender_id == user.id,
                    Connection.created_at >= start_datetime,
                    Connection.created_at <= end_datetime
                )
            )
        ) or 0
        
        # Calculate session duration (simplified)
        session_duration = await self._calculate_session_duration(
            user.id, start_datetime, end_datetime
        )
        
        # Count page views
        page_views = await self._count_user_events(
            user.id, AnalyticsEventType.PAGE_VIEW, start_datetime, end_datetime
        )
        
        # Count searches
        searches_performed = await self._count_user_events(
            user.id, AnalyticsEventType.SEARCH_PERFORMED, start_datetime, end_datetime
        )
        
        # Calculate profile completion score
        profile_completion = await self._calculate_profile_completion(user)
        
        # Check if user has profile picture
        has_profile_picture = bool(user.profile_image_url)
        
        if existing_analytics:
            # Update existing analytics
            await self.db.execute(
                update(UserAnalytics).where(
                    UserAnalytics.id == existing_analytics.id
                ).values(
                    login_count=login_count,
                    posts_created=posts_created,
                    comments_made=comments_made,
                    likes_given=likes_given,
                    connections_made=connections_made,
                    session_duration_minutes=session_duration,
                    page_views=page_views,
                    searches_performed=searches_performed,
                    profile_completion_score=profile_completion,
                    has_profile_picture=has_profile_picture,
                    updated_at=datetime.utcnow()
                )
            )
        else:
            # Create new analytics record
            user_analytics = UserAnalytics(
                user_id=user.id,
                date=target_date,
                login_count=login_count,
                posts_created=posts_created,
                comments_made=comments_made,
                likes_given=likes_given,
                connections_made=connections_made,
                session_duration_minutes=session_duration,
                page_views=page_views,
                searches_performed=searches_performed,
                profile_completion_score=profile_completion,
                has_profile_picture=has_profile_picture,
                last_activity=user.last_active_at or datetime.utcnow()
            )
            self.db.add(user_analytics)
    
    async def compute_daily_platform_analytics(self, target_date: date = None) -> None:
        """Compute daily platform-wide analytics"""
        if target_date is None:
            target_date = date.today() - timedelta(days=1)  # Process previous day
        
        try:
            logger.info(f"Computing daily platform analytics for {target_date}")
            
            start_datetime = datetime.combine(target_date, datetime.min.time())
            end_datetime = datetime.combine(target_date, datetime.max.time())
            
            # Total users
            total_users = await self.db.scalar(
                select(func.count(User.id)).where(User.is_active == True)
            ) or 0
            
            # New signups
            new_signups = await self.db.scalar(
                select(func.count(User.id)).where(
                    and_(
                        User.created_at >= start_datetime,
                        User.created_at <= end_datetime
                    )
                )
            ) or 0
            
            # Daily active users
            daily_active_users = await self.db.scalar(
                select(func.count(func.distinct(UserAnalytics.user_id))).where(
                    and_(
                        UserAnalytics.date == target_date,
                        UserAnalytics.login_count > 0
                    )
                )
            ) or 0
            
            # Weekly active users (last 7 days)
            week_ago = target_date - timedelta(days=7)
            weekly_active_users = await self.db.scalar(
                select(func.count(func.distinct(UserAnalytics.user_id))).where(
                    and_(
                        UserAnalytics.date >= week_ago,
                        UserAnalytics.date <= target_date,
                        UserAnalytics.login_count > 0
                    )
                )
            ) or 0
            
            # Monthly active users (last 30 days)
            month_ago = target_date - timedelta(days=30)
            monthly_active_users = await self.db.scalar(
                select(func.count(func.distinct(UserAnalytics.user_id))).where(
                    and_(
                        UserAnalytics.date >= month_ago,
                        UserAnalytics.date <= target_date,
                        UserAnalytics.login_count > 0
                    )
                )
            ) or 0
            
            # Content metrics
            total_posts = await self.db.scalar(
                select(func.count(Post.id)).where(
                    and_(
                        Post.created_at >= start_datetime,
                        Post.created_at <= end_datetime,
                        Post.deleted == False
                    )
                )
            ) or 0
            
            total_comments = await self.db.scalar(
                select(func.count(PostComment.id)).where(
                    and_(
                        PostComment.created_at >= start_datetime,
                        PostComment.created_at <= end_datetime
                    )
                )
            ) or 0
            
            total_likes = await self.db.scalar(
                select(func.count(PostReaction.user_id)).where(
                    and_(
                        PostReaction.created_at >= start_datetime,
                        PostReaction.created_at <= end_datetime
                    )
                )
            ) or 0
            
            total_connections = await self.db.scalar(
                select(func.count(Connection.id)).where(
                    and_(
                        Connection.created_at >= start_datetime,
                        Connection.created_at <= end_datetime
                    )
                )
            ) or 0
            
            # Session metrics
            average_session_duration = await self.db.scalar(
                select(func.avg(UserAnalytics.session_duration_minutes)).where(
                    and_(
                        UserAnalytics.date == target_date,
                        UserAnalytics.session_duration_minutes > 0
                    )
                )
            ) or 0.0
            
            # Total page views
            total_page_views = await self.db.scalar(
                select(func.sum(UserAnalytics.page_views)).where(
                    UserAnalytics.date == target_date
                )
            ) or 0
            
            # Geographic and industry data
            geographic_data = await self._get_geographic_data(target_date)
            industry_data = await self._get_industry_data(target_date)
            
            # Check if platform analytics already exist
            existing_platform_analytics = await self.db.scalar(
                select(PlatformAnalytics).where(
                    PlatformAnalytics.date == target_date
                )
            )
            
            if existing_platform_analytics:
                # Update existing record
                await self.db.execute(
                    update(PlatformAnalytics).where(
                        PlatformAnalytics.id == existing_platform_analytics.id
                    ).values(
                        total_users=total_users,
                        new_signups=new_signups,
                        daily_active_users=daily_active_users,
                        weekly_active_users=weekly_active_users,
                        monthly_active_users=monthly_active_users,
                        total_posts=total_posts,
                        total_comments=total_comments,
                        total_likes=total_likes,
                        total_connections=total_connections,
                        average_session_duration=average_session_duration,
                        total_page_views=total_page_views,
                        geographic_data=geographic_data,
                        industry_data=industry_data,
                        updated_at=datetime.utcnow()
                    )
                )
            else:
                # Create new record
                platform_analytics = PlatformAnalytics(
                    date=target_date,
                    total_users=total_users,
                    new_signups=new_signups,
                    daily_active_users=daily_active_users,
                    weekly_active_users=weekly_active_users,
                    monthly_active_users=monthly_active_users,
                    total_posts=total_posts,
                    total_comments=total_comments,
                    total_likes=total_likes,
                    total_connections=total_connections,
                    average_session_duration=average_session_duration,
                    total_page_views=total_page_views,
                    geographic_data=geographic_data,
                    industry_data=industry_data
                )
                self.db.add(platform_analytics)
            
            await self.db.commit()
            logger.info(f"Completed daily platform analytics for {target_date}")
            
        except Exception as e:
            logger.error(f"Error computing daily platform analytics: {str(e)}")
            await self.db.rollback()
            raise
    
    async def compute_content_analytics(self, target_date: date = None) -> None:
        """Compute content analytics for all posts"""
        if target_date is None:
            target_date = date.today() - timedelta(days=1)
        
        try:
            logger.info(f"Computing content analytics for {target_date}")
            
            start_datetime = datetime.combine(target_date, datetime.min.time())
            end_datetime = datetime.combine(target_date, datetime.max.time())
            
            # Get all posts created on the target date
            posts_query = select(Post).where(
                and_(
                    Post.created_at >= start_datetime,
                    Post.created_at <= end_datetime,
                    Post.deleted == False
                )
            )
            posts_result = await self.db.execute(posts_query)
            posts = posts_result.scalars().all()
            
            for post in posts:
                await self._compute_post_analytics(post, target_date)
            
            await self.db.commit()
            logger.info(f"Completed content analytics for {target_date}")
            
        except Exception as e:
            logger.error(f"Error computing content analytics: {str(e)}")
            await self.db.rollback()
            raise
    
    async def _compute_post_analytics(self, post: Post, target_date: date) -> None:
        """Compute analytics for a single post"""
        start_datetime = datetime.combine(target_date, datetime.min.time())
        end_datetime = datetime.combine(target_date, datetime.max.time())
        
        # Count engagements for the day
        likes = await self.db.scalar(
            select(func.count(PostReaction.user_id)).where(
                and_(
                    PostReaction.post_id == post.id,
                    PostReaction.created_at >= start_datetime,
                    PostReaction.created_at <= end_datetime
                )
            )
        ) or 0
        
        comments = await self.db.scalar(
            select(func.count(PostComment.id)).where(
                and_(
                    PostComment.post_id == post.id,
                    PostComment.created_at >= start_datetime,
                    PostComment.created_at <= end_datetime
                )
            )
        ) or 0
        
        bookmarks = await self.db.scalar(
            select(func.count(Bookmark.id)).where(
                and_(
                    Bookmark.post_id == post.id,
                    Bookmark.created_at >= start_datetime,
                    Bookmark.created_at <= end_datetime
                )
            )
        ) or 0
        
        # Calculate engagement rate and virality score
        total_engagements = likes + comments + bookmarks
        engagement_rate = total_engagements / max(1, post.engagement.get("view_count", 1))
        virality_score = self._calculate_virality_score(likes, comments, bookmarks)
        
        # Check if content analytics already exist
        existing_content_analytics = await self.db.scalar(
            select(ContentAnalytics).where(
                and_(
                    ContentAnalytics.post_id == post.id,
                    ContentAnalytics.date == target_date
                )
            )
        )
        
        if existing_content_analytics:
            # Update existing record
            await self.db.execute(
                update(ContentAnalytics).where(
                    ContentAnalytics.id == existing_content_analytics.id
                ).values(
                    likes=likes,
                    comments=comments,
                    bookmarks=bookmarks,
                    engagement_rate=engagement_rate,
                    virality_score=virality_score,
                    updated_at=datetime.utcnow()
                )
            )
        else:
            # Create new record
            content_analytics = ContentAnalytics(
                post_id=post.id,
                date=target_date,
                likes=likes,
                comments=comments,
                bookmarks=bookmarks,
                engagement_rate=engagement_rate,
                virality_score=virality_score
            )
            self.db.add(content_analytics)
    
    async def compute_cohort_analytics(self) -> None:
        """Compute cohort analysis data"""
        try:
            logger.info("Computing cohort analytics")
            
            # Get all cohort months (months when users signed up)
            cohort_months_query = select(
                func.date_trunc('month', User.created_at).label('cohort_month')
            ).distinct().where(User.is_active == True)
            
            cohort_months_result = await self.db.execute(cohort_months_query)
            cohort_months = [row.cohort_month.date() for row in cohort_months_result.all()]
            
            current_month = date.today().replace(day=1)
            
            for cohort_month in cohort_months:
                await self._compute_cohort_month_analytics(cohort_month, current_month)
            
            await self.db.commit()
            logger.info("Completed cohort analytics")
            
        except Exception as e:
            logger.error(f"Error computing cohort analytics: {str(e)}")
            await self.db.rollback()
            raise
    
    async def _compute_cohort_month_analytics(self, cohort_month: date, current_month: date) -> None:
        """Compute analytics for a specific cohort month"""
        # Get users in this cohort
        cohort_users_query = select(User.id).where(
            and_(
                func.date_trunc('month', User.created_at) == cohort_month,
                User.is_active == True
            )
        )
        cohort_users_result = await self.db.execute(cohort_users_query)
        cohort_user_ids = [row.id for row in cohort_users_result.all()]
        
        if not cohort_user_ids:
            return
        
        users_in_cohort = len(cohort_user_ids)
        
        # Calculate retention for each month since cohort
        month_diff = (current_month.year - cohort_month.year) * 12 + (current_month.month - cohort_month.month)
        
        for period in range(min(month_diff + 1, 12)):  # Up to 12 months
            period_month = cohort_month + timedelta(days=30 * period)
            
            # Count active users in this period
            active_users = await self.db.scalar(
                select(func.count(func.distinct(UserAnalytics.user_id))).where(
                    and_(
                        UserAnalytics.user_id.in_(cohort_user_ids),
                        func.date_trunc('month', UserAnalytics.date) == period_month,
                        UserAnalytics.login_count > 0
                    )
                )
            ) or 0
            
            retention_rate = (active_users / users_in_cohort) * 100 if users_in_cohort > 0 else 0
            
            # Check if cohort analytics already exist
            existing_cohort_analytics = await self.db.scalar(
                select(CohortAnalytics).where(
                    and_(
                        CohortAnalytics.cohort_month == cohort_month,
                        CohortAnalytics.period_number == period
                    )
                )
            )
            
            if existing_cohort_analytics:
                # Update existing record
                await self.db.execute(
                    update(CohortAnalytics).where(
                        CohortAnalytics.id == existing_cohort_analytics.id
                    ).values(
                        users_in_cohort=users_in_cohort,
                        active_users=active_users,
                        retention_rate=retention_rate,
                        updated_at=datetime.utcnow()
                    )
                )
            else:
                # Create new record
                cohort_analytics = CohortAnalytics(
                    cohort_month=cohort_month,
                    period_number=period,
                    users_in_cohort=users_in_cohort,
                    active_users=active_users,
                    retention_rate=retention_rate
                )
                self.db.add(cohort_analytics)
    
    # Helper methods
    async def _count_user_events(
        self, 
        user_id: str, 
        event_type: AnalyticsEventType, 
        start_time: datetime, 
        end_time: datetime
    ) -> int:
        """Count events for a user in a time period"""
        count = await self.db.scalar(
            select(func.count(AnalyticsEvent.id)).where(
                and_(
                    AnalyticsEvent.user_id == user_id,
                    AnalyticsEvent.event_type == event_type.value,
                    AnalyticsEvent.timestamp >= start_time,
                    AnalyticsEvent.timestamp <= end_time
                )
            )
        )
        return count or 0
    
    async def _calculate_session_duration(
        self, 
        user_id: str, 
        start_time: datetime, 
        end_time: datetime
    ) -> float:
        """Calculate total session duration for a user in a time period"""
        # This is a simplified calculation
        # In reality, you'd track session start/end events
        session_events = await self.db.execute(
            select(AnalyticsEvent.timestamp).where(
                and_(
                    AnalyticsEvent.user_id == user_id,
                    AnalyticsEvent.event_type.in_([
                        AnalyticsEventType.SESSION_START,
                        AnalyticsEventType.SESSION_END
                    ]),
                    AnalyticsEvent.timestamp >= start_time,
                    AnalyticsEvent.timestamp <= end_time
                )
            ).order_by(AnalyticsEvent.timestamp)
        )
        
        timestamps = [row.timestamp for row in session_events.all()]
        
        if len(timestamps) < 2:
            return 0.0
        
        # Calculate session duration (simplified)
        total_minutes = 0.0
        for i in range(0, len(timestamps) - 1, 2):
            if i + 1 < len(timestamps):
                duration = (timestamps[i + 1] - timestamps[i]).total_seconds() / 60
                total_minutes += duration
        
        return total_minutes
    
    async def _calculate_profile_completion(self, user: User) -> float:
        """Calculate profile completion score for a user"""
        score = 0.0
        total_fields = 8  # Adjust based on your profile fields
        
        if user.full_name:
            score += 1
        if user.bio:
            score += 1
        if user.profile_image_url:
            score += 1
        if user.job_title:
            score += 1
        if user.company:
            score += 1
        if user.industry:
            score += 1
        if user.location:
            score += 1
        if user.linkedin_profile:
            score += 1
        
        return (score / total_fields) * 100
    
    def _calculate_virality_score(self, likes: int, comments: int, bookmarks: int) -> float:
        """Calculate virality score based on engagement metrics"""
        # Simple virality calculation
        # You can make this more sophisticated based on your needs
        return (likes * 0.3 + comments * 0.5 + bookmarks * 0.2)
    
    async def _get_geographic_data(self, target_date: date) -> Dict[str, Any]:
        """Get geographic usage data for a specific date"""
        # This would implement logic to get geographic data
        # For now, return empty dict
        return {}
    
    async def _get_industry_data(self, target_date: date) -> Dict[str, Any]:
        """Get industry usage data for a specific date"""
        # This would implement logic to get industry data
        # For now, return empty dict
        return {}


# Background task functions to be called by scheduler
async def run_daily_analytics_tasks():
    """Run all daily analytics tasks"""
    async for db in get_db():
        service = AnalyticsTasksService(db)
        
        # Run tasks for yesterday
        yesterday = date.today() - timedelta(days=1)
        
        await service.compute_daily_user_analytics(yesterday)
        await service.compute_daily_platform_analytics(yesterday)
        await service.compute_content_analytics(yesterday)
        
        break  # Only need one database session


async def run_weekly_analytics_tasks():
    """Run weekly analytics tasks"""
    async for db in get_db():
        service = AnalyticsTasksService(db)
        
        await service.compute_cohort_analytics()
        
        break  # Only need one database session
