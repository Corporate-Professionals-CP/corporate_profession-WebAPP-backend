"""
Complete Post CRUD operations with:
- Full compliance
- User relationship handling
- Improved feed algorithms
- Better error handling
"""

from typing import List, Optional, Tuple, Union
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, case, and_, or_, func, desc, cast, JSON, Float, type_coerce, delete

from fastapi import HTTPException, status
from app.models.post import Post, PostStatus, PostEngagement, PostPublic
from app.models.post_comment import PostComment
from app.models.bookmark import Bookmark
from app.models.post_reaction import ReactionType, PostReaction
from app.models.user import User
from app.models.skill import Skill
from app.models.follow import UserFollow
from app.models.connection import Connection
from app.schemas.post import PostCreate, PostUpdate, PostSearch, PostRead, ReactionBreakdown, PostSearchResponse, UserReactionStatus
from app.schemas.enums import Industry, PostType, PostVisibility
from app.core.security import get_current_active_user
from sqlalchemy.orm import selectinload, Mapped
from collections import defaultdict
from app.models.notification import Notification
from app.crud.notification import create_notification
from app.schemas.enums import NotificationType

async def create_post(
    session: AsyncSession,
    post_data: PostCreate,
    current_user: User
) -> Post:
    """
    Optimized post creation with enhanced validation and error handling
    """
    try:
        # Validate media URLs if provided
        if post_data.media_urls:
            for url in post_data.media_urls:
                if not url.startswith("https://storage.googleapis.com/"):
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid media URL format"
                    )

        # Determine media type
        media_type = None
        if post_data.media_urls:
            if len(post_data.media_urls) > 1:
                media_type = "multiple"
            else:
                url = post_data.media_urls[0]
                media_type = "video" if any(ext in url for ext in [".mp4", ".mov"]) else "image"

        # Create dictionary of post data
        post_dict = post_data.dict(exclude_unset=True, exclude={"tags", "skills", "media_urls"})

        # Add media fields
        post_dict.update({
            "media_url": ",".join(post_data.media_urls) if post_data.media_urls else None,
            "media_type": media_type
        })

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
        
        # Convert media_url to media_urls for response
        if db_post.media_url:
            db_post.media_urls = db_post.media_url.split(',')
        else:
            db_post.media_urls = []
            
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
    Update post with ownership and validation checks.
    Supports media updates. Admin privileges apply.
    """
    db_post = await get_post_with_user(session, post_id)
    post, author = db_post

    # Authorization check
    if str(author.id) != str(current_user.id) and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this post"
        )

    # Validate job post industry
    if (post.post_type == PostType.JOB_POSTING and
        post_update.industry is None and
        post.industry is None and
        post.job_title is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Job posts must maintain industry specification"
        )

    update_data = post_update.dict(exclude_unset=True, exclude={"media_urls"})

    # Handle media updates
    media_urls = post_update.media_urls
    if media_urls is not None:
        for url in media_urls:
            if not url.startswith("https://storage.googleapis.com/"):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid media URL format"
                )
        post.media_url = ",".join(media_urls) if media_urls else None
        if len(media_urls) > 1:
            post.media_type = "multiple"
        elif len(media_urls) == 1:
            post.media_type = "video" if any(ext in media_urls[0] for ext in [".mp4", ".mov"]) else "image"
        else:
            post.media_type = None

    for field, value in update_data.items():
        setattr(post, field, value)

    post.updated_at = datetime.utcnow()

    try:
        session.add(post)
        await session.commit()
        await session.refresh(post)

        # Set media_urls field for response
        post.media_urls = post.media_url.split(',') if post.media_url else []

        return post
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update post: {str(e)}"
        )

async def repost_post(
    session: AsyncSession,
    original_post_id: UUID,
    current_user: User,
    quote_text: Optional[str] = None,
    media_urls: Optional[List[str]] = None
) -> Post:
    """Create a Twitter-style quote repost using only full_name"""
    # Get original post with owner
    result = await session.execute(
        select(Post)
        .options(selectinload(Post.user))
        .where(Post.id == str(original_post_id))
    )
    original_post = result.scalar_one_or_none()
    
    if not original_post:
        raise HTTPException(status_code=404, detail="Original post not found")

    # Get original poster's display name (using only full_name)
    original_poster = original_post.user
    display_name = original_poster.full_name if original_poster.full_name else "a user"

    # Twitter-style formatting
    content = quote_text.strip() if quote_text else None
    title = None  # Don't use title for quote reposts

    # Store original post data
    original_post_info = {
        "id": str(original_post.id),
        "title": original_post.title,
        "content": original_post.content,
        "user": {
            "id": str(original_poster.id),
            "full_name": original_poster.full_name or ""
        },
        "media_urls": original_post.media_url.split(',') if original_post.media_url else []
    }

    # Validate media
    media_type = None
    if media_urls:
        for url in media_urls:
            str_url = str(url)
            if not str_url.startswith("https://storage.googleapis.com/"):
                raise HTTPException(400, "Invalid media URL format")
        
        media_type = (
            "multiple" if len(media_urls) > 1 else
            "video" if any(ext in str(media_urls[0]).lower() for ext in [".mp4", ".mov"]) else
            "image"
        )

    repost = Post(
        title=title,
        content=content,  # Just the quote text
        post_type=original_post.post_type,
        is_repost=True,
        is_quote_repost=bool(quote_text),
        original_post_id=str(original_post.id),
        original_post_info=original_post_info,
        user_id=str(current_user.id),
        visibility=PostVisibility.PUBLIC,
        media_url=",".join([str(u) for u in media_urls]) if media_urls else None,
        media_type=media_type,
        engagement=PostEngagement().dict(),
        published_at=datetime.utcnow()
    )

    # Update original post engagement
    if not hasattr(original_post, 'engagement'):
        original_post.engagement = {}
    original_post.engagement["share_count"] = original_post.engagement.get("share_count", 0) + 1

    session.add(repost)
    await session.commit()
    await session.refresh(repost)
    
    # For response
    repost.media_urls = repost.media_url.split(',') if repost.media_url else []
    
    return repost


async def undo_repost_operation(
    session: AsyncSession,
    repost_id: UUID,
    current_user: User
) -> bool:
    """CRUD operation to delete a repost"""
    try:
        # Get the repost with original post loaded
        result = await session.execute(
            select(Post)
            .options(selectinload(Post.original_post))
            .where(Post.id == str(repost_id))
            .where(Post.user_id == str(current_user.id))
            .where(Post.is_repost == True)
        )
        repost = result.scalar_one_or_none()
        
        if not repost:
            return False

        # Decrement share count on original
        if repost.original_post:
            if isinstance(repost.original_post.engagement, dict):
                repost.original_post.engagement["share_count"] = max(
                    0,
                    repost.original_post.engagement.get("share_count", 1) - 1
                )
            else:
                repost.original_post.engagement = {"share_count": 0}

        # Delete associated notification if reference_id exists
        if hasattr(Notification, 'reference_id'):
            await session.execute(
                delete(Notification).where(
                    and_(
                        Notification.reference_id == str(repost_id),
                        Notification.type == NotificationType.POST_REPOST
                    )
                )
            )

        # Delete the repost
        await session.delete(repost)
        await session.commit()
        return True

    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to undo repost: {str(e)}"
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
    """Enhanced feed algorithm with immediate visibility for new posts"""
    # Cursor parsing
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

    # Time thresholds for post prioritization
    very_recent_threshold = datetime.utcnow() - timedelta(minutes=15)
    recent_threshold = datetime.utcnow() - timedelta(hours=6)

    # Get followed users first
    followed_users = await session.execute(
        select(UserFollow.followed_id)
        .where(UserFollow.follower_id == str(current_user.id))
    )
    followed_ids = [str(u[0]) for u in followed_users.all()]

    # Engagement score calculation with NULL protection
    engagement_score = (
        func.coalesce(Post.engagement["view_count"].astext.cast(Float), 0) * 0.4 +
        func.coalesce(Post.engagement["bookmark_count"].astext.cast(Float), 0) * 0.6
    ).label("engagement_score")

    priority_score = case(
        # Highest priority: Very recent posts from followed users or matching interests
        (
            and_(
                Post.created_at > very_recent_threshold,
                or_(
                    Post.user_id == str(current_user.id),
                    Post.user_id.in_(followed_ids),
                    Post.skills.any(Skill.id.in_([s.id for s in current_user.skills])),
                    and_(
                        Post.industry == current_user.industry,
                        Post.visibility.in_(["public", "industry"])
                    )
                )
            ),
            10000  # Highest priority
        ),
        # Medium priority: Recent posts
        (
            Post.created_at > recent_threshold,
            5000 + engagement_score  # Boost recent posts
        ),
        else_=engagement_score  # Default to engagement score for older posts
    ).label("priority_score")

    # Base query conditions
    base_conditions = [
        Post.status == PostStatus.PUBLISHED,
        Post.is_active == True,
        Post.deleted == False,
        or_(
            Post.expires_at.is_(None),
            Post.expires_at > datetime.utcnow()
        )
    ]
    
    if post_type:
        base_conditions.append(Post.post_type == post_type)
    if cutoff_date:
        base_conditions.append(Post.created_at >= cutoff_date)

    # Never exclude very recent posts from feed
    if exclude_ids:
        base_conditions.append(
            or_(
                Post.id.not_in(exclude_ids),
                Post.created_at > very_recent_threshold
            )
        )

    # Build the complete query
    query = (
        select(
            Post,
            User,
            priority_score
        )
        .join(User)
        .where(and_(*base_conditions))
        .order_by(
            desc("priority_score"),
            desc(Post.created_at),
            desc(Post.id)
        )
        .limit(limit + 5)  # Get extra for pagination
    )

    # Execute query
    result = await session.execute(query)
    posts = result.all()

    # Generate cursor
    next_cursor = None
    if len(posts) > limit:
        last_post = posts[limit - 1][0]
        next_cursor = f"{last_post.created_at.isoformat()},{last_post.id}"

    return posts[:limit], [], next_cursor

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
    post = result.scalar_one_or_none()

    if not post:
        return None

    # Ensure media_urls is populated for response
    post.media_urls = post.media_url.split(',') if post.media_url else []
    
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
    db: AsyncSession,
    user_id: UUID,
    include_inactive: bool = False,
    current_user: User = None,
    offset: int = 0,
    limit: int = 50
) -> Tuple[List[Post], List[User]]:
    """
    Retrieve posts by a specific user along with associated user data.
    Supports inactive post filtering and pagination.
    Returns:
        Tuple[List[Post], List[User]]: Posts and their matching authors (in order)
    """

    query = select(Post).where(Post.user_id == str(user_id))  # Convert UUID to string here

    if not include_inactive:
        query = query.where(Post.is_active == True)

    query = query.order_by(Post.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    posts = result.scalars().all()

    if not posts:
        return [], []

    # Collect all unique user_ids (in this case just one, but generalized)
    user_ids = {post.user_id for post in posts}

    user_result = await db.execute(
        select(User).where(User.id.in_(user_ids))
    )
    
    # Fix the issue here: iterate correctly over the result
    user_map = {user_result.id: user_result for user_result in user_result.scalars().all()}

    # Match each post to the correct user
    users = [user_map.get(post.user_id) for post in posts]

    return posts, users


async def search_posts(
    db: AsyncSession,
    search: Optional[str] = None,
    industry: Optional[str] = None,
    experience_level: Optional[str] = None,
    job_title: Optional[str] = None,
    post_type: Optional[str] = None,
    skills: Optional[List[str]] = None,
    limit: int = 10,
    cursor_time: Optional[datetime] = None,
    cursor_id: Optional[UUID] = None
) -> PostSearchResponse:
    # Build search & filter conditions
    relevance_conditions = []
    filter_conditions = []

    if search:
        search_term = f"%{search.lower()}%"
        relevance_conditions.append(func.lower(Post.title).like(search_term))
        relevance_conditions.append(func.lower(Post.content).like(search_term))

    if industry:
        filter_conditions.append(Post.industry == industry)
    if experience_level:
        filter_conditions.append(Post.experience_level == experience_level)
    if job_title:
        filter_conditions.append(Post.job_title == job_title)
    if post_type:
        filter_conditions.append(Post.post_type == post_type)
    if skills:
        for skill in skills:
            filter_conditions.append(Post.skills.any(Skill.name.ilike(f"%{skill}%")))

    # Base query to get post IDs (pagination applied here)
    subquery_stmt = select(Post.id).join(User).where(Post.status == PostStatus.PUBLISHED)

    if relevance_conditions:
        subquery_stmt = subquery_stmt.where(or_(*relevance_conditions))
    if filter_conditions:
        subquery_stmt = subquery_stmt.where(and_(*filter_conditions))
    if cursor_time and cursor_id:
        subquery_stmt = subquery_stmt.where(
            or_(
                Post.created_at < cursor_time,
                and_(Post.created_at == cursor_time, Post.id < cursor_id)
            )
        )

    subquery_stmt = subquery_stmt.order_by(Post.created_at.desc(), Post.id.desc()).limit(limit)
    subquery = subquery_stmt.subquery()

    # Main query: get full posts and user details
    main_query = (
        select(Post, User)
        .join(User)
        .options(selectinload(Post.skills))
        .where(Post.id.in_(select(subquery.c.id)))
        .order_by(Post.created_at.desc(), Post.id.desc())
    )

    result = await db.execute(main_query)
    posts = result.all()

    if not posts:
        return PostSearchResponse(results=[], next_cursor=None)

    post_objs = [p for p, _ in posts]
    user_objs = [u for _, u in posts]

    enriched_results = await enrich_multiple_posts(db, post_objs, user_objs)

    # Add media_urls to each enriched result
    for enriched_post, raw_post in zip(enriched_results, post_objs):
        if hasattr(raw_post, 'media_url') and raw_post.media_url:
            enriched_post.media_urls = raw_post.media_url.split(',')
        else:
            enriched_post.media_urls = []


    last_post = post_objs[-1]
    next_cursor = f"{last_post.created_at.isoformat()}_{last_post.id}" if len(post_objs) == limit else None

    return PostSearchResponse(
        results=enriched_results,
        next_cursor=next_cursor
    )


async def search_jobs_by_criteria(
    session: AsyncSession,
    current_user: Optional[User] = None,
    query: Optional[str] = None,
    skill: Optional[Union[str, List[str]]] = None,
    location: Optional[str] = None,
    experience: Optional[str] = None,
    job_title: Optional[str] = None,
    offset: int = 0,
    limit: int = 100
) -> List[Post]:
    """
    Search for job postings based on multiple criteria: skill, location, experience, and job title.
    If `current_user` follows someone, only their posts are shown; otherwise, posts from all users.
    """
    stmt = (
        select(Post)
        .where(Post.post_type == PostType.JOB_POSTING)
        .options(selectinload(Post.skills))
    )

    # Filter to followed users if applicable
    if current_user:
        followed_users = await session.execute(
            select(UserFollow.followed_id)
            .where(UserFollow.follower_id == str(current_user.id))
        )
        followed_ids = [str(u[0]) for u in followed_users.all()]
        if followed_ids:
            stmt = stmt.where(Post.user_id.in_(followed_ids))

    # Keyword query on title/content
    if query:
        stmt = stmt.where(
            or_(
                Post.title.ilike(f"%{query}%"),
                Post.content.ilike(f"%{query}%")
            )
        )

    # Skill filtering
    if skill:
        skill_list = [skill] if isinstance(skill, str) else skill
        stmt = stmt.where(or_(*[Post.skills.any(name=s) for s in skill_list]))

    # Location filtering
    if location:
        stmt = stmt.where(Post.location.ilike(f"%{location}%"))

    # Experience filtering
    if experience:
        stmt = stmt.where(Post.experience_level == experience)

    # Job title filtering
    if job_title:
        stmt = stmt.where(Post.title.ilike(f"%{job_title}%"))

    # Sorting & pagination
    stmt = stmt.order_by(Post.created_at.desc()).offset(offset).limit(limit)

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

async def enrich_multiple_posts(
    db: AsyncSession,
    posts: List[Post],
    users: List[User],
    current_user_id: Optional[str] = None
) -> List[PostRead]:
    post_ids = [str(post.id) for post in posts]

    # Bulk fetch reaction counts
    reaction_counts = await db.execute(
        select(
            PostReaction.post_id,
            PostReaction.type,
            func.count(PostReaction.user_id)
        ).where(PostReaction.post_id.in_(post_ids))
        .group_by(PostReaction.post_id, PostReaction.type)
    )
    reaction_map = {}
    for pid, rtype, count in reaction_counts.all():
        reaction_map.setdefault(pid, {})[rtype] = count

    # Bulk fetch user's reactions if authenticated
    user_reactions_map = {}
    if current_user_id:
        user_reactions = await db.execute(
            select(PostReaction.post_id, PostReaction.type)
            .where(
                PostReaction.post_id.in_(post_ids),
                PostReaction.user_id == current_user_id
            )
        )
        for pid, rtype in user_reactions.all():
            user_reactions_map.setdefault(pid, set()).add(rtype)

    # Comments (existing)
    comment_data = await db.execute(
        select(PostComment.post_id, func.count(PostComment.id))
        .where(PostComment.post_id.in_(post_ids))
        .group_by(PostComment.post_id)
    )
    comment_map = {pid: count for pid, count in comment_data.all()}

    # Bookmarks (existing)
    bookmark_map = {}
    if current_user_id:
        bookmark_data = await db.execute(
            select(Bookmark.post_id, func.count(Bookmark.id))
            .where(
                Bookmark.post_id.in_(post_ids),
                Bookmark.user_id == current_user_id
            )
            .group_by(Bookmark.post_id)
        )
        bookmark_map = {str(pid): count for pid, count in bookmark_data.all()}

    # Assemble enriched posts
    enriched = []
    for post, user in zip(posts, users):
        post_id_str = str(post.id)
        
        # Build reactions breakdown with user status
        reactions_breakdown = ReactionBreakdown()
        total_reactions = 0
        
        for rtype in ReactionType:
            count = reaction_map.get(post_id_str, {}).get(rtype, 0)
            has_reacted = rtype in user_reactions_map.get(post_id_str, set())
            
            # Set the reaction status
            setattr(reactions_breakdown, rtype, UserReactionStatus(
                count=count,
                has_reacted=has_reacted
            ))
            
            total_reactions += count

        enriched_data = {
            **post.__dict__,
            "user": user,
            "total_comments": comment_map.get(post_id_str, 0),
            "total_reactions": total_reactions,
            "is_bookmarked": bookmark_map.get(post_id_str, 0) > 0,
            "reactions_breakdown": reactions_breakdown,
            "has_reacted": any(
                getattr(reactions_breakdown, rtype).has_reacted
                for rtype in ReactionType
            ),
            "is_active": post.is_active,
            "bookmark_count": bookmark_map.get(post_id_str, 0)
        }
        
        enriched.append(PostRead(**enriched_data))

    return enriched

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

async def get_reactions_breakdown(
    db: AsyncSession,
    post_id: UUID,
    current_user_id: Optional[UUID] = None
) -> ReactionBreakdown:
    # Get all reactions for this post
    reactions = await get_reactions_for_post(db, post_id)

    breakdown = ReactionBreakdown()

    # Count reactions and check if current user reacted
    for reaction in reactions:
        # Update count
        reaction_type = reaction.type.value  # e.g., "like", "love"
        getattr(breakdown, reaction_type).count += 1

        # Check if current user reacted
        if current_user_id and reaction.user_id == current_user_id:
            getattr(breakdown, reaction_type).has_reacted = True

    return breakdown
