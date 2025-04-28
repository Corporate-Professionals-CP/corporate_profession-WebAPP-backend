"""
post endpoints implementation
- Post creation
- Feed display
- Post management
"""

from uuid import UUID
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.db.database import get_db
from app.models.user import User
from app.models.post import PostType
from app.schemas.post import PostCreate, PostRead, PostUpdate, PostSearch
from app.crud.post import (
    create_post,
    get_post,
    update_post,
    delete_post,
    get_feed_posts,
    get_posts_by_user,
    search_posts
)
from app.core.security import get_current_active_user, get_current_active_admin
from app.core.config import settings

router = APIRouter(prefix="/posts", tags=["posts"])

@router.post("/", response_model=PostRead, status_code=status.HTTP_201_CREATED)
async def create_new_post(
    *,
    post_in: PostCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new post in the system.
    Any user can create posts
    
    Post Types:
    - job: Job opportunities (must include industry tag)
    - announcement: Professional announcements
    - update: Career updates
    
    Required Fields:
    - title: 5-100 characters
    - content: 10-2000 characters
    - post_type: One of [job, announcement, update]
    - industry: Required for job posts
    """
    # Validate job posts have industry specified
    if post_in.post_type == PostType.JOB_POSTING and not post_in.industry:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Job posts must specify an industry"
        )
    
    try:
        return await create_post(db, post_in, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

@router.get("/feed/", response_model=List[PostRead])
async def read_feed(
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
    offset: int = Query(0, ge=0),
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get personalized feed according to requirements:
    - Shows posts from user's industry + general posts
    - Ordered by newest first
    - Filterable by post type and recency
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=recent_days) if recent_days else None

        posts = await get_feed_posts(
            session=db,
            current_user=current_user,
            post_type=post_type,
            cutoff_date=cutoff_date,
            offset=offset,
            limit=limit
        )

        if not posts:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No posts found in your feed"
            )

        return [
            PostRead(
                id=post.id,
                title=post.title,
                content=post.content,
                post_type=post.post_type,
                industry=post.industry,
                is_active=post.is_active,
                created_at=post.created_at,
                updated_at=post.updated_at,
                user=user
            )
            for post, user in posts
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving feed: {str(e)}"
        )


@router.post("/search", response_model=List[PostRead])
async def search_posts_endpoint(
    search_params: PostSearch,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Advanced post search with multiple filters
    """
    posts = await search_posts(
        session=db,
        current_user=current_user,
        query=search_params.query,
        industry=search_params.industry,
        post_type=search_params.post_type,
        created_after=search_params.created_after,
        end_date=search_params.end_date,
        offset=search_params.offset,
        limit=search_params.limit
    )
    
    if not posts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No posts found matching your criteria"
        )
    
    return [
        PostRead(
            id=post.id,
            title=post.title,
            content=post.content,
            post_type=post.post_type,
            industry=post.industry,
            is_active=post.is_active,
            created_at=post.created_at,
            updated_at=post.updated_at,
            user=user
        )
        for post, user in posts
    ]

@router.get("/user/{user_id}", response_model=List[PostRead])
async def read_user_posts(
    user_id: UUID,
    include_inactive: bool = Query(
        False,
        description="Include inactive posts (admin only)"
    ),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieve posts by a specific user with pagination
    User content visibility
    """
    # Only allow admins to see inactive posts
    if include_inactive and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view inactive posts"
        )
    
    posts = await get_posts_by_user(
        db,
        user_id,
        include_inactive=include_inactive,
        offset=offset,
        limit=limit
    )
    
    if not posts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No posts found for this user"
        )

    response_posts = []
    for post in posts:
        post_data = PostRead.from_orm(post)
        if not post.user.hide_profile:
            post_data.user = {
                "name": post.user.full_name,
                "job_title": post.user.job_title,
                "company": post.user.company
            }
        response_posts.append(post_data)

    return response_posts

@router.get("/{post_id}", response_model=PostRead)
async def read_post(
    post_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed view of a single post
    Post visibility
    """
    post = await get_post(db, post_id)
    if not post or not post.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    return post

@router.put("/{post_id}", response_model=PostRead)
async def update_existing_post(
    post_id: UUID,
    post_in: PostUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update an existing post.
    Post management
    
    Rules:
    - Only the post author can update their posts
    - Admins can update any post
    - Job posts must maintain industry tag
    """
    post = await get_post(db, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    
    # Validate job posts maintain industry
    if post_in.post_type == PostType.JOB_POSTING and not post_in.industry:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Job posts must specify an industry"
        )
    
    updated_post = await update_post(db, post_id, post_in, current_user)
    if not updated_post:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this post"
        )
    return updated_post

@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_post(
    post_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a post (soft delete).
    Post management
    
    Rules:
    - Post author can delete their own posts
    - Admins can delete any post
    """
    try:
        success = await delete_post(db, post_id, current_user)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
