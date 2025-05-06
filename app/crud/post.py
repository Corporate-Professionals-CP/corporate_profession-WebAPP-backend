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
from sqlalchemy import select, and_, or_, func, desc, cast, JSON, Float, type_coerce

from fastapi import HTTPException, status
from app.models.post import Post, PostStatus, PostEngagement, PostPublic
from app.models.user import User
from app.models.skill import Skill
from app.models.follow import UserFollow
from app.schemas.post import PostCreate, PostUpdate, PostSearch, PostRead
from app.schemas.enums import Industry, PostType, JobTitle, PostVisibility
from app.core.security import get_current_active_user
from sqlalchemy.orm import selectinload, Mapped

async def create_post(
    session: AsyncSession,
    post_data: PostCreate,
    current_user: User
) -> Post:
    """
    Optimized post creation with enhanced validation and error handling
    """
    try:
        # Create dictionary of post data
        post_dict = post_data.dict(exclude_unset=True, exclude={"tags", "skills"})

        # Handle job post validations
        if post_data.post_type == PostType.JOB_POSTING:
            if not post_data.industry:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Job posts must specify an industry"
                )
            post_dict.setdefault("expires_at", datetime.utcnow() + timedelta(days=30))

        # Resolve skills first
        resolved_skills = await _resolve_skills(session, post_data.skills)

        # Create post instance
        db_post = Post(
            **post_dict,
            user_id=str(current_user.id),
            skills=resolved_skills,
            tags=post_data.tags or [],
            engagement=PostEngagement().dict(),
            status=PostStatus.PUBLISHED,
            published_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        session.add(db_post)
        await session.flush()
        
        # Eager load relationships needed for response
        result = await session.execute(
            select(Post)
            .options(
                selectinload(Post.skills),
                selectinload(Post.user)
            )
            .where(Post.id == db_post.id)
        )
        db_post = result.scalar_one()
        
        await session.commit()
        return db_post

    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create post: {str(e)}"
        )


async def _resolve_skills(session: AsyncSession, skill_names: List[str]) -> List[Skill]:
    """Get or create skills by name"""
    if not skill_names:
        return []

    # Case-insensitive search
    stmt = select(Skill).where(
        func.lower(Skill.name).in_([name.lower() for name in skill_names])
    )
    result = await session.execute(stmt)
    existing_skills = result.scalars().all()

    # Find new skills needed
    existing_names = {s.name.lower() for s in existing_skills}
    new_skills = [
        Skill(name=name.title())  # Ensure consistent capitalization
        for name in skill_names
        if name.lower() not in existing_names
    ]

    # Add new skills if any
    if new_skills:
        session.add_all(new_skills)
        await session.flush()
        existing_skills.extend(new_skills)

    # Return the list of Skill objects
    return existing_skills

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
    cursor: Optional[str] = None,
    cutoff_date: Optional[datetime] = None,
    limit: int = 50,
    exclude_ids: Optional[List[UUID]] = None
) -> Tuple[List[Tuple[Post, User]], Optional[str]]:
    """Enhanced feed algorithm with engagement scoring and fresh posts"""
    # Cursor parsing and base query setup
    cursor_time, cursor_id = None, None
    if cursor:
        try:
            cursor_time_str, cursor_id = cursor.split(",")
            cursor_time = datetime.fromisoformat(cursor_time_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cursor format"
            )

    # Calculate engagement score
    engagement_score = (
        (Post.engagement["view_count"].astext.cast(Float) * 0.4) +
        (Post.engagement["bookmark_count"].astext.cast(Float) * 0.6)
    ).label("engagement_score")

    # Base query with scoring
    query = (
        select(
            Post,
            User,
            engagement_score
        )
        .join(User)
        .distinct(Post.id)
        .where(Post.status == PostStatus.PUBLISHED)
        .where(Post.is_active == True)
        .where(Post.deleted == False)
        .where(or_(
            Post.expires_at.is_(None),
            Post.expires_at > datetime.utcnow()
        ))
        .where(
            (Post.post_type == post_type) if post_type
            else True
        )
        .where(
            (Post.created_at >= cutoff_date) if cutoff_date
            else True
        )
    )

    # Exclusion of already seen posts
    if exclude_ids:
        query = query.where(Post.id.not_in(exclude_ids))

    # Followed users condition
    followed_users = await session.execute(
        select(UserFollow.followed_id)
        .where(UserFollow.follower_id == str(current_user.id))
    )
    followed_ids = [str(u[0]) for u in followed_users.all()]

    # Relevance conditions with priority
    relevance_conditions = [
        # Highest priority: Followed users
        Post.user_id.in_(followed_ids),
        
        # Medium priority: Industry match
        and_(
            Post.industry == current_user.industry,
            Post.visibility.in_(["public", "industry"])
        ),
        
        # Skill-based matches
        Post.skills.any(Skill.id.in_([s.id for s in current_user.skills]))
    ]

    # Add public posts condition
    relevance_conditions.append(
        and_(
            Post.industry.is_(None),
            Post.visibility == "public"
        )
    )

    query = query.where(or_(*relevance_conditions))

    # Cursor pagination
    if cursor_time and cursor_id:
        query = query.where(
            or_(
                Post.created_at < cursor_time,
                and_(
                    Post.created_at == cursor_time,
                    Post.id < cursor_id
                )
            )
        )

    # Execute with engagement-based ordering
    result = await session.execute(
        query.order_by(
            desc(Post.id),
            desc("engagement_score"),
            desc(Post.created_at)
        )
        .limit(limit + 3)  # Get extra for freshness check
    )
    posts = result.all()

    # Split into fresh and main posts
    fresh_posts = [
        p for p in posts 
        if p[0].created_at > datetime.utcnow() - timedelta(minutes=5)
    ]
    main_posts = [p for p in posts if p not in fresh_posts][:limit]

    # Generate cursor
    next_cursor = None
    if main_posts:
        last_post = main_posts[-1][0]
        next_cursor = f"{last_post.created_at.isoformat()},{last_post.id}"

    return main_posts, fresh_posts[:3], next_cursor

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
    cursor: Optional[str] = None,
    limit: int = 100
) -> Tuple[List[Tuple[Post, User]], Optional[str]]:
    """Enhanced search with cursor pagination and relevance"""
    # Cursor parsing (same as get_feed_posts)
    cursor_time = None
    cursor_id = None
    if cursor:
        try:
            cursor_time_str, cursor_id = cursor.split(",")
            cursor_time = datetime.fromisoformat(cursor_time_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cursor format"
            )

    # Build base query
    query_stmt = (
        select(Post, User)
        .join(User)
        .options(selectinload(Post.skills))
        .distinct(Post.id)
        .where(Post.status == PostStatus.PUBLISHED)
    )

    # Search relevance weights
    relevance_conditions = []
    if query:
        search_terms = query.split()
        for term in search_terms:
            term_pattern = f"%{term}%"
            relevance_conditions.extend([
                Post.title.ilike(term_pattern),
                Post.content.ilike(term_pattern),
                Post.skills.any(Skill.name.ilike(term_pattern))
            ])

    # Apply filters
    filter_conditions = []
    if industry:
        filter_conditions.append(Post.industry == industry)
    if post_type:
        filter_conditions.append(Post.post_type == post_type)

    # Combine conditions
    if relevance_conditions:
        query_stmt = query_stmt.where(or_(*relevance_conditions))
    if filter_conditions:
        query_stmt = query_stmt.where(and_(*filter_conditions))

    # Cursor pagination
    if cursor_time and cursor_id:
        query_stmt = query_stmt.where(
            or_(
                Post.created_at < cursor_time,
                and_(
                    Post.created_at == cursor_time,
                    Post.id < cursor_id
                )
            )
        )

    # Execute query
    result = await session.execute(
        query_stmt.order_by(Post.created_at.desc(), Post.id.desc())
        .limit(limit)
    )
    posts = result.all()

    # Generate next cursor
    next_cursor = None
    if posts:
        last_post = posts[-1][0]
        next_cursor = f"{last_post.created_at.isoformat()},{last_post.id}"

    return posts, next_cursor

async def search_jobs_by_criteria(
    session: AsyncSession,
    current_user: Optional[User] = None,
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

    if current_user:
        followed_users = await session.execute(
            select(UserFollow.followed_id)
            .where(UserFollow.follower_id == str(current_user.id))
        )
        followed_ids = [str(u[0]) for u in followed_users.all()]

        
    stmt = select(Post).where(Post.post_type == PostType.JOB_POSTING)
    stmt = stmt.where(
            or_(
                Post.user_id.in_(followed_ids),
            )
        )

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

async def get_multi(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 100,
    include_inactive: bool = False,
    include_deleted: bool = False
) -> List[Post]:
    """Get multiple posts with pagination"""
    query = select(Post).options(selectinload(Post.user))
    
    if not include_inactive:
        query = query.where(Post.is_active == True)
    if not include_deleted:
        query = query.where(Post.deleted == False)
        
    result = await session.execute(
        query.order_by(Post.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
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
