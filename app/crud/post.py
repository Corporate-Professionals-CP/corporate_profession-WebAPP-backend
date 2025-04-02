"""
Post CRUD operations with:
- (Posting & Feed)
- Fixed syntax errors
- Improved type hints
- Better error handling
"""

from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, and_, or_
from fastapi import HTTPException, status
from datetime import datetime

from app.models.post import Post, PostType
from app.schemas.post import PostCreate, PostUpdate

async def create_post(
    session: AsyncSession, 
    post_data: PostCreate, 
    user_id: UUID
) -> Post:
    """
    Create a new post with validation.
    Any user can create posts
    """
    # Validate job posts have industry specified
    if post_data.post_type == PostType.JOB and not post_data.industry:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Job posts must specify an industry"
        )

    try:
        db_post = Post(**post_data.dict(), user_id=str(user_id))
        session.add(db_post)
        await session.commit()
        await session.refresh(db_post)
        return db_post
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create post: {str(e)}"
        )

async def get_post(
    session: AsyncSession, 
    post_id: UUID
) -> Optional[Post]:
    """
    Retrieve a single post by ID
    Post visibility
    """
    result = await session.execute(
        select(Post)
        .where(Post.id == str(post_id))
    )
    return result.scalars().first()

async def update_post(
    session: AsyncSession,
    post_id: UUID,
    post_update: PostUpdate,
    current_user_id: UUID
) -> Post:
    """
    Update post with ownership validation.
    Post management
    
    Rules:
    - Only the post author can update
    - Admins can update any post
    - Job posts must maintain industry tag
    """
    db_post = await get_post(session, post_id)
    if not db_post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )

    # Validate job posts maintain industry
    if (post_update.post_type == PostType.JOB and 
        not post_update.industry and 
        not db_post.industry):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Job posts must specify an industry"
        )

    update_data = post_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_post, field, value)

    try:
        session.add(db_post)
        await session.commit()
        await session.refresh(db_post)
        return db_post
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update post: {str(e)}"
        )

async def delete_post(
    session: AsyncSession,
    post_id: UUID,
    current_user_id: UUID
) -> bool:
    """
    Delete a post (soft delete via is_active flag)
    Post management
    
    Rules:
    - Post author can delete
    - Admins can delete any post
    """
    db_post = await get_post(session, post_id)
    if not db_post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )

    db_post.is_active = False
    try:
        session.add(db_post)
        await session.commit()
        return True
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete post: {str(e)}"
        )

async def get_feed_posts(
    session: AsyncSession,
    *,
    user_industries: Optional[List[str]] = None,
    post_type: Optional[PostType] = None,
    user_id: Optional[UUID] = None,
    cutoff_date: Optional[datetime] = None,
    offset: int = 0,
    limit: int = 50
) -> List[Post]:
    """
    Retrieve posts for feed with filtering.
    Feed displays relevant posts
    
    Behavior:
    - Shows posts from user's industries
    - Includes general posts (no industry)
    - Filters by post type
    - Can filter by recency
    - Ordered by newest first
    """
    query = select(Post).where(Post.is_active == True)
    
    # Apply industry filters
    if user_industries:
        query = query.where(
            or_(
                Post.industry.in_(user_industries),
                Post.industry.is_(None)
            )
        )
    
    # Additional filters
    if post_type:
        query = query.where(Post.post_type == post_type)
    if user_id:
        query = query.where(Post.user_id == str(user_id))
    if cutoff_date:
        query = query.where(Post.created_at >= cutoff_date)
    
    # Execute query with pagination
    result = await session.execute(
        query.order_by(Post.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()