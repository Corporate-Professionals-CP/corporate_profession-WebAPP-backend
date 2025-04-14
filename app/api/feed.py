"""
feed endpoints
(Posting & Feed)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from sqlmodel import select, or_, and_
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import Optional
from app.db.database import get_db
from app.models.post import Post, PostType
from app.schemas.post import PostRead, PostCreate
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/feed", tags=["feed"])

class FeedFilters(BaseModel):
    """Optional filters for feed customization"""
    post_types: Optional[List[PostType]] = None
    industries: Optional[List[str]] = None
    time_range: Optional[int] = None  # Days to look back
    search_query: Optional[str] = None

@router.get("/", response_model=List[PostRead])
async def get_personalized_feed(
    offset: int = 0,
    limit: int = 20,
    filters: FeedFilters = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    professional feed with enhanced filtering
    PRD Requirements:
    - Shows industry-relevant posts
    - Includes general posts
    - Supports post type filtering
    - Newest posts first with configurable time range
    - Pagination supported
    """
    # Base query - active posts sorted newest first
    query = select(Post).where(Post.is_active == True)
    
    # Apply time range filter if specified
    if filters.time_range:
        cutoff_date = datetime.utcnow() - timedelta(days=filters.time_range)
        query = query.where(Post.created_at >= cutoff_date)
    
    # Apply industry filtering
    industry_filters = []
    if current_user and current_user.industry:
        industry_filters.append(Post.industry == current_user.industry)
    
    # Include general posts and any additional requested industries
    industry_filters.append(Post.industry == None)
    if filters.industries:
        industry_filters.extend([Post.industry == ind for ind in filters.industries])
    
    query = query.where(or_(*industry_filters))
    
    # Apply post type filtering if specified
    if filters.post_types:
        query = query.where(Post.post_type.in_(filters.post_types))
    
    # Apply search query if specified
    if filters.search_query:
        query = query.where(
            or_(
                Post.title.ilike(f"%{filters.search_query}%"),
                Post.content.ilike(f"%{filters.search_query}%")
            )
        )
    
    # Finalize query with sorting and pagination
    result = await db.execute(
        query.order_by(Post.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    posts = result.scalars().all()

    if not posts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No posts available matching your criteria"
        )

    return posts

@router.post("/", response_model=PostRead, status_code=status.HTTP_201_CREATED)
async def create_post(
    post_data: PostCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new post for the professional feed
    Requirements:
    - Any user can create posts
    - Posts can be tagged by industry
    """
    post = Post(**post_data.dict(), user_id=current_user.id)
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return post
