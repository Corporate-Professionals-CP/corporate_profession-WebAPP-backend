"""
feed endpoints (Posting & Feed)
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
from app.db.database import get_db
from app.models.post import Post, PostType
from app.schemas.post import PostRead
from app.core.security import get_current_user
from app.crud.post import get_feed_posts
from app.models.user import User
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
    post_type: Optional[PostType] = Query(
        None,
        description="Filter by post type: job, announcement, or update"
    ),
    recent_days: Optional[int] = Query(
        None,
        ge=1,
        le=365,
        description="Filter posts from last N days"
    ),
    cursor: Optional[str] = Query(
        None,
        description="Pagination cursor (format: 'timestamp,post_id')"
    ),
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Personalized feed with:
    - Followed users' posts
    - Industry-relevant content
    - Skill-matched posts
    - Engagement-based ranking
    - Fresh posts highlight
    - Cursor pagination
    """
    try:
        # Calculate cutoff date if needed
        cutoff_date = (datetime.utcnow() - timedelta(days=recent_days)) if recent_days else None

        # Get seen posts from cookies
        exclude_ids = get_seen_posts_from_request(request)

        # Get enhanced feed posts
        main_posts, fresh_posts, next_cursor = await get_feed_posts(
            session=db,
            current_user=current_user,
            post_type=post_type,
            cutoff_date=cutoff_date,
            cursor=cursor,
            limit=limit,
            exclude_ids=exclude_ids
        )

        # Track seen posts in cookies
        new_post_ids = [str(post[0].id) for post in main_posts + fresh_posts]
        track_seen_posts(response, new_post_ids)

        # Convert to response models
        def create_post_read(post, user):
            return PostRead(
                id=post.id,
                title=post.title,
                content=post.content,
                post_type=post.post_type,
                industry=post.industry,
                is_active=post.is_active,
                created_at=post.created_at,
                updated_at=post.updated_at,
                user=user,
                engagement=post.engagement,
                skills=[s.name for s in post.skills]
            )

        return FeedResponse(
            main_posts=[create_post_read(p, u) for p, u in main_posts],
            fresh_posts=[create_post_read(p, u) for p, u in fresh_posts],
            next_cursor=next_cursor
        )

    except HTTPException as e:
        raise e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Feed retrieval failed: {str(e)}"
        )
