"""
feed endpoints (Posting & Feed)
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from sqlalchemy import select, or_, and_
from pydantic import BaseModel
from datetime import datetime, timedelta
from app.db.database import get_db
from app.models.post import Post, PostType, PostStatus
from app.schemas.post import PostRead
from app.core.security import get_current_user
from app.crud.post import get_feed_posts, enrich_multiple_posts
from app.models.user import User
from app.models.follow import UserFollow
from app.utils.feed_cookies import (
    track_seen_posts,
    get_seen_posts_from_request
)

router = APIRouter(prefix="/feed", tags=["feed"])

class FeedResponse(BaseModel):
    main_posts: List[PostRead]
    fresh_posts: List[PostRead]
    next_cursor: Optional[str] = None

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
    Personalized feed curated by:
    - Followed users
    - Shared topics (tags)
    - Industry relevance
    Includes:
    - Engagement scoring
    - Fresh posts
    - Enriched data (comments, reactions)
    """

    try:
        cutoff_date = datetime.utcnow() - timedelta(days=recent_days) if recent_days else None
        exclude_ids = get_seen_posts_from_request(request)

        # Parse cursor
        cursor_time, cursor_id = None, None
        if cursor:
            try:
                cursor_time_str, cursor_id = cursor.split(",")
                cursor_time = datetime.fromisoformat(cursor_time_str)
            except ValueError:
                raise HTTPException(400, "Invalid cursor format")

        # Get followed users
        followed_q = await db.execute(
            select(UserFollow.followed_id).where(UserFollow.follower_id == current_user.id)
        )
        followed_ids = [str(row[0]) for row in followed_q.all()]

        # Base query
        stmt = (
            select(Post, User)
            .join(User)
            .where(
                Post.deleted == False,
                Post.status == PostStatus.PUBLISHED,
                Post.is_active == True
            )
        )

        # Filters
        conditions = []

        if post_type:
            conditions.append(Post.post_type == post_type)

        if current_user.topics:
            conditions.append(Post.tags.overlap(current_user.topics))

        if current_user.industry:
            conditions.append(Post.industry == current_user.industry)

        # Include followed users’ posts
        if followed_ids:
            conditions.append(Post.user_id.in_(followed_ids))

        stmt = stmt.where(or_(*conditions))

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
        enriched_posts = await enrich_multiple_posts(db, posts, users)

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
        raise HTTPException(500, detail=f"Feed error: {str(e)}")





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
    Get posts only from followed users or based on shared interests (topics)
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
                raise HTTPException(400, "Invalid cursor format")

        stmt = (
            select(Post, User)
            .join(User)
            .where(
                Post.deleted == False,
                Post.status == PostStatus.PUBLISHED,
                Post.is_active == True,
                Post.user_id != current_user.id
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
        enriched_posts = await enrich_multiple_posts(db, posts, users)

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
        raise HTTPException(500, detail=f"Network feed error: {str(e)}")
