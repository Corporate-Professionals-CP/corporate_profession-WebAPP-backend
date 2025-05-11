"""
feed endpoints (Posting & Feed)
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
from app.db.database import get_db
from app.models.post import Post, PostType, PostStatus
from app.schemas.post import PostRead
from app.core.security import get_current_user
from app.crud.post import get_feed_posts, enrich_post_data
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
                Post.status == "published",
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
        posts = result.all()

        async def enrich_pair(post_user):
            post, user = post_user
            post.user = user
            enriched = await enrich_post_data(db, post)
            return PostRead(**enriched)

        enriched_posts = [await enrich_pair(pu) for pu in posts[:limit]]

        next_cursor = None
        if len(posts) > limit:
            last_post = posts[limit - 1][0]
            next_cursor = f"{last_post.created_at.isoformat()},{last_post.id}"

        # Track seen posts
        seen_ids = [str(p[0].id) for p in posts]
        track_seen_posts(response, seen_ids)

        return FeedResponse(
            main_posts=enriched_posts,
            fresh_posts=[],
            next_cursor=next_cursor
        )

    except Exception as e:
        raise HTTPException(500, detail=f"Feed failed: {str(e)}")




@router.get("/network", response_model=FeedResponse)
async def get_network_feed(
    request: Request,
    response: Response,
    cursor: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get posts only from followed users or based on shared interests (topics)
    """
    # Get followed users
    followed_users = await db.execute(
        select(UserFollow.followed_id).where(UserFollow.follower_id == current_user.id)
    )
    followed_ids = [str(row[0]) for row in followed_users.all()]

    # Query posts
    stmt = (
        select(Post, User)
        .join(User)
        .where(
            or_(
                Post.user_id.in_(followed_ids),
                Post.tags.overlap(current_user.topics or [])  # topic overlap from signup
            ),
            Post.deleted == False,
            Post.status == "published"
        )
        .order_by(Post.created_at.desc())
        .limit(limit)
    )

    results = await db.execute(stmt)
    posts = results.all()

    # Enrich
    async def enrich_pair(post_user):
        post, user = post_user
        post.user = user
        return PostRead(**await enrich_post_data(db, post))

    enriched = [await enrich_pair(pu) for pu in posts]

    return FeedResponse(
        main_posts=enriched,
        fresh_posts=[],
        next_cursor=None
    )

