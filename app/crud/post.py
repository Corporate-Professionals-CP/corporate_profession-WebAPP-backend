"""
Complete Post CRUD operations with:
- Full compliance
- User relationship handling
- Improved feed algorithms
- Better error handling
"""

from typing import List, Optional, Tuple
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from fastapi import HTTPException, status
import sqlalchemy
from app.models.post import Post, PostStatus, PostEngagement, PostPublic
from app.models.user import User
from app.schemas.post import PostCreate, PostUpdate, PostSearch, PostRead
from app.schemas.enums import Industry, PostType, JobTitle, PostVisibility
from app.core.security import get_current_active_user
from sqlalchemy.orm import selectinload

async def create_post(
    session: AsyncSession,
    post_data: PostCreate,
    current_user: User
) -> Post:
    """
    Optimized post creation with enhanced validation and error handling
    """
    # Create dictionary of post data for cleaner manipulation
    post_dict = post_data.dict(exclude_unset=True, exclude={"tags"})
    
    # Handle job post specific validations
    if post_data.post_type == PostType.JOB_POSTING:
        if not post_data.industry:
            if not post_data.job_title:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Job posts must specify an industry"
            )
        post_dict.setdefault("expires_at", datetime.utcnow() + timedelta(days=30))

    # Create post instance with all required fields
    db_post = Post(
        **post_dict,
        user_id=str(current_user.id),
        tags=post_data.tags or [],
        engagement=PostEngagement().dict(),
        status=PostStatus.PUBLISHED,
        published_at=datetime.utcnow(),
        updated_at=datetime.utcnow() 
    )

    try:
        async with session.begin():
            session.add(db_post)
            await session.flush()
            await session.refresh(db_post, ["user"])
            
            # Increment user's post count if needed
            if hasattr(db_post.user, 'post_count'):
                db_post.user.post_count += 1
                session.add(db_post.user)
            
            return db_post
            
    except sqlalchemy.exc.IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Database integrity error occurred"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create post: {str(e)}"
        )

async def get_post_with_user(
    session: AsyncSession,
    post_id: UUID
) -> Tuple[Post, User]:
    """
    Retrieve post with author information
    Post visibility rules
    """
    result = await session.execute(
        select(Post, User)
        .join(User)
        .where(Post.id == str(post_id))
        .where(Post.is_active)
    )
    post_user = result.first()
    
    if not post_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found or inactive"
        )
    
    return post_user

async def update_post(
    session: AsyncSession,
    post_id: UUID,
    post_update: PostUpdate,
    current_user: User
) -> Post:
    """
    Update post with ownership and validation checks
    Admin privileges
    """
    db_post = await get_post_with_user(session, post_id)
    post, author = db_post

    # Authorization check
    if str(author.id) != str(current_user.id) and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this post"
        )

    # Job post validation
    if (post.post_type == PostType.JOB_POSTING and 
        post_update.industry is None and 
        post.industry is None and
        post.job_title is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Job posts must maintain industry specification"
        )

    update_data = post_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(post, field, value)

    post.updated_at = datetime.utcnow()

    try:
        session.add(post)
        await session.commit()
        await session.refresh(post)
        return post
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update post: {str(e)}"
        )

async def delete_post(
    session: AsyncSession,
    post_id: UUID,
    current_user: User
) -> bool:
    """
    Soft delete post using deleted flag (respects ClassVar is_active)
    """

    logger.info(f"User {current_user.id} soft-deleted post {post_id}")


    # First retrive the post with author
    result = await session.execute(
        select(Post)
        .options(selectinload(Post.user))
        .where(Post.id == str(post_id))
    )
    post = result.scalar_one_or_none()

    if not post:
        return False

    # Authorization check
    if str(post.user.id) != str(current_user.id) and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this post"
        )

    # Perform soft delete - only modify the deleted flag
    try:
        post.deleted = True 
        post.updated_at = datetime.utcnow()
        session.add(post)
        await session.commit()
        return True
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete post: {str(e)}"
        )

async def get_filtered_posts(
    session: AsyncSession,
    *,
    is_active: Optional[bool] = None,
    industry: Optional[Industry] = None,
    offset: int = 0,
    limit: int = 100
) -> List[Post]:
    """
    Admin-only: Get posts with no visibility/industry restrictions.
    """
    query = select(Post).options(selectinload(Post.user))

    if is_active is not None:
        query = query.where(Post.is_active == is_active)
    if industry:
        query = query.where(Post.industry == industry)

    result = await session.execute(
        query.order_by(Post.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()

async def get_feed_posts(
    session: AsyncSession,
    current_user: User,
    *,
    post_type: Optional[PostType] = None,
    cutoff_date: Optional[datetime] = None,
    offset: int = 0,
    limit: int = 50
) -> List[Tuple[Post, User]]:
    """
    Get feed posts according to specifications:
    - Includes posts from user's industry AND general posts
    - Respects post visibility settings
    - Filters by type and date if specified
    """
    query = (
        select(Post, User)
        .join(User)
        .where(Post.status == PostStatus.PUBLISHED)
        .where(Post.is_active == True)
        .where(Post.deleted == False)
        .where(
            or_(
                Post.expires_at.is_(None),
                Post.expires_at > datetime.utcnow()
            )
        )
    )

    # Apply visibility rules
    query = query.where(
        or_(
            # Posts from user's industry
            and_(
                Post.industry == current_user.industry,
                Post.visibility.in_(["public", "industry"])
            ),
            # General posts (no industry specified)
            and_(
                Post.industry.is_(None),
                Post.visibility == "public"
            ),
            # User's own posts
            Post.user_id == str(current_user.id)
        )
    )

    # Apply post type filter
    if post_type:
        query = query.where(Post.post_type == post_type)

    # Apply recency filter
    if cutoff_date:
        query = query.where(Post.created_at >= cutoff_date)

    # Final ordering and pagination
    result = await session.execute(
        query.order_by(Post.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    return result.all()

async def get_post(
    session: AsyncSession,
    post_id: UUID,
    current_user: Optional[User] = None
) -> Optional[Post]:
    """
    Retrieve a single post with visibility enforcement.
    """
    query = (
        select(Post)
        .options(selectinload(Post.user))
        .where(Post.deleted == False)
        .where(Post.id == str(post_id))
        .where(Post.is_active == True)
    )

    if current_user:
        # Restrict access based on visibility
        query = query.where(
            or_(
                Post.visibility == "public",
                and_(
                    Post.visibility == "industry",
                    Post.industry == current_user.industry
                ),
                Post.user_id == str(current_user.id),
                current_user.is_admin  # Admins can see all
            )
        )

    result = await session.execute(query)
    return result.scalar_one_or_none()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    
    return post

async def get_post_by_id_admin(
    session: AsyncSession,
    post_id: UUID
) -> Optional[Post]:
    """Admin version - gets post without visibility checks"""
    result = await session.execute(
        select(Post)
        .options(selectinload(Post.user))
        .where(Post.id == str(post_id))
        .where(Post.deleted == False)  # Only non deleted post 
    )
    return result.scalar_one_or_none()

async def get_posts_by_user(
    session: AsyncSession,
    user_id: UUID,
    *,
    include_inactive: bool = False,
    current_user: Optional[User] = None,
    offset: int = 0,
    limit: int = 100
) -> List[Post]:
    """
    Get user's posts with visibility controls
    Profile visibility
    """
    query = (
        select(Post, User)
        .options(selectinload(Post.user))
        .where(Post.deleted == False)
        .join(User)
        .where(User.id == str(user_id))
    )

    if not include_inactive:
        query = query.where(Post.is_active == True)

    # Visibility controls
    if current_user and str(current_user.id) != str(user_id):
        query = query.where(
            or_(
                Post.visibility == "public",
                and_(
                    Post.visibility == "industry",
                    User.industry == current_user.industry
                )
            )
        )

    result = await session.execute(
        query.order_by(Post.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    
    return result.scalars().all()

async def search_posts(
    session: AsyncSession,
    *,
    current_user: Optional[User] = None,
    query: Optional[str] = None,
    industry: Optional[Industry] = None,
    post_type: Optional[PostType] = None,
    job_title: Optional[JobTitle] = None,
    created_after: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    offset: int = 0,
    limit: int = 100
) -> List[Tuple[Post, User]]:
    """
    Advanced post search with user context
    """
    query_stmt = (
        select(Post, User)
        .join(User)
        .where(Post.status == PostStatus.PUBLISHED)
    )

    # Keyword search
    if query:
        search_terms = query.split()
        conditions = []
        for term in search_terms:
            term_pattern = f"%{term}%"
            conditions.append(Post.title.ilike(term_pattern))
            conditions.append(Post.content.ilike(term_pattern))
        query_stmt = query_stmt.where(or_(*conditions)) 

    # Industry filter
    if industry:
        query_stmt = query_stmt.where(Post.industry == industry)

    # Job Title
    if job_title:
        query_smt = query_smt.where(post.job_title == job_title)

    # Post type filter
    if post_type:
        query_stmt = query_stmt.where(Post.post_type == post_type)

    # Date range
    if created_after:
        query_stmt = query_stmt.where(Post.created_at >= created_after)
    if end_date:
        query_stmt = query_stmt.where(Post.created_at <= end_date)

    # Visibility controls
    if current_user:
        query_stmt = query_stmt.where(
            or_(
                Post.visibility == "public",
                and_(
                    Post.visibility == "industry",
                    User.industry == current_user.industry
                ),
                Post.user_id == str(current_user.id)
            )
        )

    result = await session.execute(
        query_stmt.order_by(Post.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    posts = result.all()
    if not posts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No posts found matching your criteria"
        )

    return posts

async def search_jobs_by_criteria(
    session: AsyncSession,
    skill: Optional[str] = None,
    location: Optional[str] = None,
    experience: Optional[str] = None,
    job_title: Optional[str] = None,
    offset: int = 0,
    limit: int = 100
) -> List[Post]:
    """
    Search for job postings based on multiple criteria: skill, location, experience, and job title.
    """
    stmt = select(Post).where(Post.post_type == PostType.JOB_POSTING)

    # Filter by skill if provided
    if skill:
        stmt = stmt.where(Post.skills.any(name=skill))

    # Filter by location if provided
    if location:
        stmt = stmt.where(Post.location.ilike(f"%{location}%"))

    # Filter by experience if provided
    if experience:
        stmt = stmt.where(Post.experience_level == experience)

    # Filter by job title if provided
    if job_title:
        stmt = stmt.where(Post.title.ilike(f"%{job_title}%"))

    stmt = stmt.offset(offset).limit(limit)

    result = await session.execute(stmt)
    return result.scalars().all()

async def increment_post_engagement(
    session: AsyncSession,
    post_id: UUID,
    engagement_type: str = "view"
) -> Post:
    """
    Track post engagement metrics
    Success metrics
    """
    post = await session.get(Post, str(post_id))
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if engagement_type == "view":
        post.engagement.view_count += 1
    elif engagement_type == "share":
        post.engagement.share_count += 1
    elif engagement_type == "bookmark":
        post.engagement.bookmark_count += 1

    try:
        session.add(post)
        await session.commit()
        await session.refresh(post)
        return post
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update engagement: {str(e)}"
        )
