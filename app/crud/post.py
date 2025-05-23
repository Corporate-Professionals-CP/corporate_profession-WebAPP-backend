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
from sqlalchemy import select, and_, or_, func, desc, cast, JSON, Float, type_coerce, delete

from fastapi import HTTPException, status
from app.models.post import Post, PostStatus, PostEngagement, PostPublic
from app.models.post_comment import PostComment
from app.models.post_reaction import ReactionType, PostReaction
from app.models.user import User
from app.models.skill import Skill
from app.models.follow import UserFollow
from app.models.connection import Connection
from app.schemas.post import PostCreate, PostUpdate, PostSearch, PostRead, ReactionBreakdown, PostSearchResponse
from app.schemas.enums import Industry, PostType, JobTitle, PostVisibility
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

async def repost_post(
    session: AsyncSession,
    original_post_id: UUID,
    current_user: User,
    quote_text: Optional[str] = None
) -> Post:
    """Create a repost (or quote-repost) of an existing post"""
    # Eager load the original post with its user
    result = await session.execute(
        select(Post)
        .options(selectinload(Post.user))
        .where(Post.id == str(original_post_id))
    )
    original_post = result.scalar_one_or_none()
    
    if not original_post:
        raise HTTPException(status_code=404, detail="Original post not found")

    # Get user identifier safely
    user_identifier = (
        original_post.user.full_name 
        if hasattr(original_post.user, 'full_name') 
        else getattr(original_post.user, 'email', 'a user').split('@')[0]
    )

    # Build content
    # Replace the content building section with:
    if quote_text:
        # Clean and format the quote text
        clean_quote = quote_text.strip()
        clean_original = original_post.content.strip()
        content = f"{clean_quote}\n\n—— Reposted from @{user_identifier} ——\n\n{clean_original}"
        title = f"Repost: {original_post.title[:50]}..." 
    else:
        content = original_post.content
        title = f"Repost: {original_post.title}"

    # Create the repost
    repost = Post(
        title=title,
        content=content,
        post_type=original_post.post_type,
        is_repost=True,
        original_post_id=str(original_post.id),
        user_id=str(current_user.id),
        visibility=PostVisibility.PUBLIC,
        tags=original_post.tags.copy() if original_post.tags else [],
        skills=original_post.skills.copy() if original_post.skills else []
    )

    # Update engagement safely
    if hasattr(original_post, 'engagement') and isinstance(original_post.engagement, dict):
        original_post.engagement["share_count"] = original_post.engagement.get("share_count", 0) + 1
    else:
        original_post.engagement = {"share_count": 1}

    session.add(repost)
    await session.commit()
    await session.refresh(repost)
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

async def enrich_multiple_posts(db: AsyncSession, posts: List[Post], users: List[User]) -> List[PostRead]:
    post_ids = [str(post.id) for post in posts]

    # Reactions (bulk fetch)
    reaction_data = await db.execute(
        select(
            PostReaction.post_id,
            PostReaction.type,
            func.count(PostReaction.user_id)
        ).where(PostReaction.post_id.in_(post_ids))
        .group_by(PostReaction.post_id, PostReaction.type)
    )
    reaction_map = {}
    for pid, rtype, count in reaction_data.all():
        if pid not in reaction_map:
            reaction_map[pid] = {}
        reaction_map[pid][rtype] = count

    # Comments (bulk fetch)
    comment_data = await db.execute(
        select(
            PostComment.post_id,
            func.count(PostComment.id)
        ).where(PostComment.post_id.in_(post_ids))
        .group_by(PostComment.post_id)
    )
    comment_map = {pid: count for pid, count in comment_data.all()}

    # Assemble enriched posts
    enriched = []
    for post, user in zip(posts, users):
        enriched_data = {
            **post.__dict__,
            "user": user,
            "total_comments": comment_map.get(str(post.id), 0),
            "total_reactions": sum(reaction_map.get(str(post.id), {}).values()),
            "reactions_breakdown": {
                r: reaction_map.get(str(post.id), {}).get(r, 0)
                for r in ReactionType.__members__.keys()
            },
            "is_active": post.is_active
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
