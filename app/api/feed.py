"""
feed endpoints (Posting & Feed)
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from sqlalchemy import select, or_, and_
from pydantic import BaseModel, field_serializer
from datetime import datetime, timedelta
from app.db.database import get_db
from app.models.post import Post, PostType, PostStatus
from app.schemas.post import PostRead
from app.core.security import get_current_user
from app.crud.post import get_feed_posts, enrich_multiple_posts
from app.crud.connection import get_my_connections
from app.models.user import User
from app.models.connection import Connection, ConnectionStatus
from app.models.follow import UserFollow
from app.utils.feed_cookies import (
    track_seen_posts,
    get_seen_posts_from_request
)
from app.core.exceptions import CustomHTTPException
from app.core.error_codes import (
    FEED_ERROR,
    NETWORK_FEED_ERROR,
    INVALID_CURSOR_FORMAT,
    UNAUTHORIZED_ACCESS,
    INVALID_REQUEST_PARAMS
)

# Setup logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Set log level

# Create console handler
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

# Add formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)

# Add handler to logger
logger.addHandler(ch)

# Now you can use it
logger.info("This is an info message")

router = APIRouter(prefix="/feed", tags=["feed"])

class FeedResponse(BaseModel):
    main_posts: List[PostRead]
    fresh_posts: List[PostRead]
    next_cursor: Optional[str] = None
    media_urls: Optional[List[str]] = None

    @field_serializer('media_urls')
    def serialize_media_urls(self, media_urls: Optional[List[str]], _info):
        """Ensure consistent serialization of media URLs"""
        if hasattr(self, 'media_url') and self.media_url:  # Handle CSV string case
            return self.media_url.split(',')
        return media_urls or []

@router.get("/", response_model=FeedResponse)
async def get_personalized_feed(
    request: Request,
    response: Response,
    post_type: Optional[PostType] = Query(None, description="Filter by post type"),
    recent_days: Optional[int] = Query(None, ge=1, le=365),
    cursor: Optional[str] = Query(None, description="Cursor format: 'timestamp,post_id'"),
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a personalized feed of posts from:
    - Followed users
    - Followers
    - Connections
    - Industry-relevant content
    """
    logger.info(f"Fetching feed for user_id={current_user.id}")
    
    try:
        # Setup filters
        cutoff_date = datetime.utcnow() - timedelta(days=recent_days) if recent_days else None
        exclude_ids = get_seen_posts_from_request(request)

        # Parse cursor for pagination
        cursor_time, cursor_id = None, None
        if cursor:
            try:
                cursor_time_str, cursor_id = cursor.split(",")
                cursor_time = datetime.fromisoformat(cursor_time_str)
            except ValueError as e:
                raise CustomHTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid cursor format: {str(e)}. Expected 'timestamp,post_id'",
                    error_code=INVALID_CURSOR_FORMAT
                )

        # Fetch related user IDs
        followed_q = await db.execute(
            select(UserFollow.followed_id).where(UserFollow.follower_id == current_user.id)
        )
        followed_ids = {str(row[0]) for row in followed_q.all()}

        followers_q = await db.execute(
            select(UserFollow.follower_id).where(UserFollow.followed_id == current_user.id)
        )
        follower_ids = {str(row[0]) for row in followers_q.all()}

        conn_q = await db.execute(
            select(Connection).where(
                Connection.status == ConnectionStatus.ACCEPTED,
                or_(
                    Connection.sender_id == current_user.id,
                    Connection.receiver_id == current_user.id
                )
            )
        )
        connections = conn_q.scalars().all()
        connection_ids = {
            str(conn.sender_id if conn.sender_id != current_user.id else conn.receiver_id)
            for conn in connections
        }

        related_user_ids = followed_ids | follower_ids | connection_ids

        # Build query
        stmt = (
            select(Post, User)
            .join(User, Post.user_id == User.id)
            .where(
                Post.deleted == False,
                Post.status == PostStatus.PUBLISHED,
                Post.is_active == True
            )
        )

        filters = []
        if post_type:
            filters.append(Post.post_type == post_type)

        if related_user_ids:
            filters.append(Post.user_id.in_(related_user_ids))

        if current_user.topics:
            filters.append(Post.engagement["tags"].contains(current_user.topics))

        if current_user.industry:
            filters.append(Post.industry == current_user.industry)

        if filters:
            stmt = stmt.where(or_(*filters))

        if cutoff_date:
            stmt = stmt.where(Post.created_at >= cutoff_date)

        if exclude_ids:
            stmt = stmt.where(Post.id.not_in(exclude_ids))

        if cursor_time and cursor_id:
            stmt = stmt.where(
                or_(
                    Post.created_at < cursor_time,
                    and_(Post.created_at == cursor_time, Post.id < cursor_id)
                )
            )

        stmt = stmt.order_by(Post.created_at.desc(), Post.id.desc()).limit(limit + 1)

        result = await db.execute(stmt)
        rows = result.all()

        seen_ids = [str(row[0].id) for row in rows]
        track_seen_posts(response, seen_ids)

        posts = [row[0] for row in rows[:limit]]
        users = [row[1] for row in rows[:limit]]

        enriched_posts = await enrich_multiple_posts(
            db,
            posts,
            users,
            current_user_id=str(current_user.id)
        )

        next_cursor = None
        if len(rows) > limit:
            last_post = rows[limit - 1][0]
            next_cursor = f"{last_post.created_at.isoformat()},{last_post.id}"

        return FeedResponse(
            main_posts=enriched_posts,
            fresh_posts=[],  # You can populate this based on separate logic if needed
            next_cursor=next_cursor
        )

    except CustomHTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in feed for user_id={current_user.id}: {str(e)}")
        raise CustomHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error while fetching feed",
            error_code=FEED_ERROR
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
    """
    Get posts only from followed users and accepted network connections.
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=recent_days) if recent_days else None
        exclude_ids = get_seen_posts_from_request(request)

        cursor_time, cursor_id = None, None
        if cursor:
            try:
                cursor_time_str, cursor_id = cursor.split(",")
                cursor_time = datetime.fromisoformat(cursor_time_str)
            except ValueError:
                raise CustomHTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid cursor format: {str(e)}. Expected 'timestamp,post_id'",
                    error_code=INVALID_CURSOR_FORMAT
                )

        user_id = str(current_user.id)

        # Get followed user IDs
        follow_stmt = select(UserFollow.followed_id).where(UserFollow.follower_id == user_id)
        follow_result = await db.execute(follow_stmt)
        followed_user_ids = set(follow_result.scalars().all())

        # Get connected user IDs (accepted connections)
        connections = await get_my_connections(db, user_id)
        connected_user_ids = set()
        for conn in connections:
            if conn.sender_id != user_id:
                connected_user_ids.add(conn.sender_id)
            elif conn.receiver_id != user_id:
                connected_user_ids.add(conn.receiver_id)

        # Combine both sets of user IDs
        allowed_user_ids = followed_user_ids.union(connected_user_ids)

        # If no followed or connected users, return empty feed
        if not allowed_user_ids:
            return FeedResponse(main_posts=[], fresh_posts=[], next_cursor=None)

        # Base query: posts by allowed users only (excluding self)
        stmt = (
            select(Post, User)
            .join(User, Post.user_id == User.id)
            .where(
                Post.deleted == False,
                Post.status == PostStatus.PUBLISHED,
                Post.is_active == True,
                Post.user_id.in_(allowed_user_ids),
                Post.user_id != user_id
            )
        )

        if post_type:
            stmt = stmt.where(Post.post_type == post_type)
        if cutoff_date:
            stmt = stmt.where(Post.created_at >= cutoff_date)
        if exclude_ids:
            stmt = stmt.where(Post.id.not_in(exclude_ids))
        if cursor_time and cursor_id:
            stmt = stmt.where(
                or_(
                    Post.created_at < cursor_time,
                    and_(
                        Post.created_at == cursor_time,
                        Post.id < cursor_id
                    )
                )
            )

        stmt = stmt.order_by(Post.created_at.desc(), Post.id.desc()).limit(limit + 1)
        result = await db.execute(stmt)
        rows = result.all()

        seen_ids = [str(row[0].id) for row in rows]
        track_seen_posts(response, seen_ids)

        posts = [row[0] for row in rows[:limit]]
        users = [row[1] for row in rows[:limit]]
        enriched_posts = await enrich_multiple_posts(
            db,
            posts,
            users,
            current_user_id=str(current_user.id) if current_user else None
        )

        next_cursor = None
        if len(rows) > limit:
            last_post = rows[limit - 1][0]
            next_cursor = f"{last_post.created_at.isoformat()},{last_post.id}"

        return FeedResponse(
            main_posts=enriched_posts,
            fresh_posts=[],
            next_cursor=next_cursor
        )

    except Exception as e:
            raise CustomHTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error retrieving network feed posts",
                error_code=NETWORK_FEED_ERROR
            )
