"""
feed endpoints (Posting & Feed)
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from sqlalchemy import select, case, or_, and_, func, desc, cast, Float, type_coerce
from pydantic import BaseModel, field_serializer
from datetime import datetime, timedelta
from app.db.database import get_db
from app.models.post import Post, PostType, PostStatus
from app.schemas.post import PostRead
from app.core.security import get_current_user
from app.crud.post import get_feed_posts, enrich_multiple_posts_optimized
from app.crud.connection import get_my_connections
from app.models.user import User
from app.models.connection import Connection, ConnectionStatus
from app.models.follow import UserFollow
from app.utils.feed_cookies import (
    track_seen_posts,
    get_seen_posts_from_request
)
from uuid import UUID
from app.core.exceptions import CustomHTTPException
from app.core.error_codes import (
    FEED_ERROR,
    NETWORK_FEED_ERROR,
    INVALID_CURSOR_FORMAT,
    UNAUTHORIZED_ACCESS,
    INVALID_REQUEST_PARAMS
)
from app.utils.cache import FeedCache

# Setup logger - simplified to work with FastAPI's logging
logger = logging.getLogger(__name__)

# Initialize feed cache
feed_cache = FeedCache(ttl_seconds=180)  # 3 minutes cache for feed

router = APIRouter(prefix="/feed", tags=["feed"])

class FeedResponse(BaseModel):
    main_posts: List[PostRead]
    fresh_posts: List[PostRead]
    next_cursor: Optional[str] = None

@router.get("/", response_model=FeedResponse)
async def get_personalized_feed(
    request: Request,
    response: Response,
    post_type: Optional[PostType] = Query(None),
    recent_days: Optional[int] = Query(None, ge=1, le=365),
    cursor: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # Create cache key based on request parameters
        cache_key = f"{post_type}:{recent_days}:{cursor}:{limit}"
        
        # Try to get from cache first
        cached_posts = feed_cache.get_feed(str(current_user.id), cache_key)
        if cached_posts:
            return FeedResponse(
                main_posts=cached_posts,
                fresh_posts=[],
                next_cursor=None  # For cached responses
            )
        
        # Get prioritized posts
        prioritized_posts, _, next_cursor = await get_feed_posts(
            db,
            current_user,
            post_type=post_type,
            cursor=cursor,
            cutoff_date=datetime.utcnow() - timedelta(days=recent_days) if recent_days else None,
            limit=limit,
            exclude_ids=get_seen_posts_from_request(request)
        )

        # Convert media URLs
        posts_for_enrich = []
        for post, user, _ in prioritized_posts:
            post.media_urls = post.media_url.split(',') if post.media_url else []
            posts_for_enrich.append((post, user))

        # Use optimized enrichment
        enriched_posts = await enrich_multiple_posts_optimized(
            db,
            [p[0] for p in posts_for_enrich],
            [p[1] for p in posts_for_enrich],
            str(current_user.id)
        )
        
        # Cache the results
        feed_cache.set_feed(str(current_user.id), cache_key, enriched_posts)

        return FeedResponse(
            main_posts=enriched_posts,
            fresh_posts=[],  # Now handled in main query
            next_cursor=next_cursor
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Feed error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch feed"
        )

@router.get("/network", response_model=FeedResponse)
async def get_network_feed(
    request: Request,
    response: Response,
    cursor: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    post_type: Optional[PostType] = Query(None),
    recent_days: Optional[int] = Query(None, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get posts from followed users and connections with recency prioritization"""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=recent_days) if recent_days else None
        user_id = str(current_user.id)

        # Time thresholds for prioritization
        very_recent_threshold = datetime.utcnow() - timedelta(minutes=15)
        recent_threshold = datetime.utcnow() - timedelta(hours=6)

        # Get seen posts from cookies
        try:
            exclude_ids = get_seen_posts_from_request(request)
        except Exception as e:
            logger.warning(f"Failed to get seen posts: {str(e)}")
            exclude_ids = []

        # Cursor handling
        cursor_time, cursor_id = None, None
        if cursor:
            try:
                cursor_time_str, cursor_id = cursor.split(",")
                cursor_time = datetime.fromisoformat(cursor_time_str)
            except ValueError as e:
                raise CustomHTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid cursor format",
                    error_code=INVALID_CURSOR_FORMAT
                )

        # Get network user IDs (followed + connected)
        follow_stmt = select(UserFollow.followed_id).where(UserFollow.follower_id == user_id)
        follow_result = await db.execute(follow_stmt)
        followed_user_ids = set(follow_result.scalars().all())

        connections = await get_my_connections(db, user_id)
        connected_user_ids = set()
        for conn in connections:
            other_user = conn.sender_id if conn.sender_id != user_id else conn.receiver_id
            connected_user_ids.add(other_user)

        allowed_user_ids = followed_user_ids.union(connected_user_ids)
        if not allowed_user_ids:
            logger.warning(f"No network connections found for user {user_id}")
            return FeedResponse(main_posts=[], fresh_posts=[], next_cursor=None)

        logger.info(f"Network feed for user {user_id}: {len(followed_user_ids)} followed, {len(connected_user_ids)} connected, {len(allowed_user_ids)} total network users")

        # Engagement score calculation
        engagement_score = (
            func.coalesce(Post.engagement["view_count"].astext.cast(Float), 0) * 0.4 +
            func.coalesce(Post.engagement["bookmark_count"].astext.cast(Float), 0) * 0.6
        ).label("engagement_score")

        # Priority score with recency boost
        priority_score = case(
            # Tier 1: Very recent posts
            (
                Post.created_at > very_recent_threshold,
                10000  # Highest priority
            ),
            # Tier 2: Recent posts
            (
                Post.created_at > recent_threshold,
                5000 + engagement_score
            ),
            else_=engagement_score
        ).label("priority_score")

        # Base query conditions
        conditions = [
            Post.deleted == False,
            Post.status == PostStatus.PUBLISHED,
            Post.user_id.in_(allowed_user_ids),
            Post.user_id != user_id,
            or_(
                Post.expires_at.is_(None),
                Post.expires_at > datetime.utcnow()
            ),
            # Visibility conditions
            or_(
                Post.visibility == "public",
                and_(
                    Post.visibility == "industry",
                    Post.industry == current_user.industry
                ),
                and_(
                    Post.visibility == "followers",
                    Post.user_id.in_(followed_user_ids)
                )
            )
        ]

        if post_type:
            conditions.append(Post.post_type == post_type)
        if cutoff_date:
            conditions.append(Post.created_at >= cutoff_date)
        if exclude_ids:
            # Convert UUID objects to strings for database compatibility
            exclude_ids_str = [str(uuid_obj) for uuid_obj in exclude_ids]
            conditions.append(
                or_(
                    Post.id.not_in(exclude_ids_str),
                    Post.created_at > very_recent_threshold
                )
            )

        # Build and execute query
        query = (
            select(Post, User, priority_score)
            .join(User)
            .where(and_(*conditions))
            .order_by(
                desc("priority_score"),
                desc(Post.created_at),
                desc(Post.id)
            )
            .limit(limit + 1)
        )

        if cursor_time and cursor_id:
            query = query.where(
                or_(
                    Post.created_at > cursor_time,
                    and_(
                        Post.created_at == cursor_time,
                        Post.id < cursor_id
                    )
                )
            )

        result = await db.execute(query)
        rows = result.all()

        logger.info(f"Network feed query returned {len(rows)} posts for user {user_id}")

        # Process results
        posts = [row[0] for row in rows[:limit]]
        users = [row[1] for row in rows[:limit]]

        # Convert media URLs
        for post in posts:
            post.media_urls = post.media_url.split(',') if post.media_url else []

        # Enrich posts
        enriched_posts = await enrich_multiple_posts_optimized(
            db, posts, users, current_user_id=user_id
        )

        # Generate cursor
        next_cursor = None
        if len(rows) > limit:
            last_post = rows[limit - 1][0]
            next_cursor = f"{last_post.created_at.isoformat()},{last_post.id}"

        # Track seen posts
        try:
            seen_ids = [str(row[0].id) for row in rows[:limit]]
            track_seen_posts(response, seen_ids)
        except Exception as e:
            logger.error(f"Failed to track seen posts: {str(e)}")

        logger.info(f"Network feed returning {len(enriched_posts)} enriched posts for user {user_id}")

        return FeedResponse(
            main_posts=enriched_posts,
            fresh_posts=[],
            next_cursor=next_cursor
        )

    except Exception as e:
        logger.error(f"Network feed error: {str(e)}", exc_info=True)
        raise CustomHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving network feed posts",
            error_code=NETWORK_FEED_ERROR
        )

@router.get("/refresh", response_model=FeedResponse)
async def refresh_feed(
    request: Request,
    response: Response,
    limit: int = Query(10, le=50),  # Smaller limit for refresh
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the most recent posts for feed refresh after creating a new post
    Returns only the freshest posts to avoid duplicates
    """
    try:
        logger.info(f"Feed refresh request for user {current_user.id}")
        
        # Get only very recent posts (last 5 minutes)
        recent_cutoff = datetime.utcnow() - timedelta(minutes=5)
        
        # Get prioritized posts
        prioritized_posts, _, _ = await get_feed_posts(
            db,
            current_user,
            cutoff_date=recent_cutoff,
            limit=limit,
            exclude_ids=[]  # Don't exclude any for refresh
        )
        
        logger.info(f"Retrieved {len(prioritized_posts)} recent posts for refresh")

        # Convert media URLs and enrich
        posts_for_enrich = []
        for post, user, _ in prioritized_posts:
            post.media_urls = post.media_url.split(',') if post.media_url else []
            posts_for_enrich.append((post, user))

        logger.info("Enriching posts for refresh...")
        enriched_posts = await enrich_multiple_posts_optimized(
            db,
            [p[0] for p in posts_for_enrich],
            [p[1] for p in posts_for_enrich],
            str(current_user.id)
        )
        
        logger.info(f"Successfully enriched {len(enriched_posts)} posts for refresh")

        return FeedResponse(
            main_posts=enriched_posts,
            fresh_posts=[],
            next_cursor=None
        )
    except Exception as e:
        logger.error(f"Feed refresh error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh feed: {str(e)}"
        )

@router.post("/refresh", status_code=200)
async def refresh_feed(
    current_user: User = Depends(get_current_user)
):
    """
    Force refresh the feed cache for the current user
    """
    try:
        feed_cache.clear_user_feed(str(current_user.id))
        
        logger.info(f"Feed cache cleared for user {current_user.id}")
        
        return {"message": "Feed cache refreshed successfully"}
    except Exception as e:
        logger.error(f"Feed refresh error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to refresh feed"
        )
