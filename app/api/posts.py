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
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import selectinload
from app.db.database import get_db
from app.models.user import User
from app.models.post import PostType
from app.schemas.post import PostCreate, PostRead, PostUpdate, PostSearch, PostSearchResponse
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
    - job_title: Required for job posts
    """

    if post_in.post_type == PostType.JOB_POSTING:
        if not post_in.job_title:
            raise HTTPException(422, "Job posts require a job title")
        if not post_in.skills:
            raise HTTPException(422, "Job posts require at least one skill")

    return await create_post(db, post_in, current_user)

@router.post("/search", response_model=PostSearchResponse)
async def search_posts_endpoint(
    search_params: PostSearch,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Advanced post search with cursor-based pagination
    ---
    Example request with cursor:
    {
        "query": "python developer",
        "industry": "TECH",
        "cursor": "2023-10-05T12:34:56.789,abc123-def456-ghi789",
        "limit": 50
    }
    """
    try:
        # Call the updated CRUD method with cursor
        posts, next_cursor = await search_posts(
            session=db,
            current_user=current_user,
            query=search_params.query,
            industry=search_params.industry,
            post_type=search_params.post_type,
            job_title=search_params.job_title,
            created_after=search_params.created_after,
            end_date=search_params.end_date,
            cursor=search_params.cursor,
            limit=search_params.limit
        )

        if not posts:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No posts found matching your criteria"
            )

        # Maintain existing serialization logic
        results = [
            PostRead(
                id=post.id,
                title=post.title,
                content=post.content,
                is_active=post.is_active,
                post_type=post.post_type,
                job_title=post.job_title,
                industry=post.industry,
                experience_level=post.experience_level,
                status=post.status,
                visibility=post.visibility,
                tags=post.tags,
                engagement=post.engagement,
                created_at=post.created_at,
                updated_at=post.updated_at,
                published_at=post.published_at,
                expires_at=post.expires_at,
                user_id=post.user_id,
                user_name=user.full_name,
                skills=[skill.name for skill in post.skills]
            )
            for post, user in posts
        ]

        return PostSearchResponse(
            results=results,
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
            detail=f"Search failed: {str(e)}"
        )

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
    if post_in.post_type == PostType.JOB_POSTING and not post_in.industry and not post_in.job_title :
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
