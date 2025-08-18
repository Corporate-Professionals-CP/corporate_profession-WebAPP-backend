from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.schemas.post_mention import (
    PostMentionResponse, MentionSuggestion, UserMentionInfo
)
from app.crud.post_mention import (
    get_post_mentions, get_user_mentions, search_users_for_mention,
    get_mention_notifications
)

router = APIRouter(prefix="/mentions", tags=["mentions"])


@router.get("/search-users", response_model=List[MentionSuggestion])
async def search_users_for_mentions(
    query: str = Query(..., min_length=2, description="Search query for users"),
    limit: int = Query(10, ge=1, le=20, description="Maximum number of suggestions"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Search users for @mention autocomplete"""
    suggestions = await search_users_for_mention(db, query, current_user.id, limit)
    return suggestions


@router.get("/posts/{post_id}", response_model=List[PostMentionResponse])
async def get_mentions_for_post(
    post_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get all mentions in a specific post"""
    mentions = await get_post_mentions(db, post_id)
    return mentions


@router.get("/my-mentions", response_model=List[PostMentionResponse])
async def get_my_mentions(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get mentions where current user was mentioned"""
    skip = (page - 1) * per_page
    mentions = await get_user_mentions(db, current_user.id, skip, per_page)
    return mentions


@router.get("/notifications")
async def get_mention_notifications_endpoint(
    unread_only: bool = Query(True, description="Show only unread notifications"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get mention notifications for current user"""
    skip = (page - 1) * per_page
    notifications = await get_mention_notifications(
        db, current_user.id, unread_only, skip, per_page
    )
    return {
        "notifications": notifications,
        "page": page,
        "per_page": per_page,
        "unread_only": unread_only
    }


@router.get("/user/{user_id}/info", response_model=UserMentionInfo)
async def get_user_mention_info(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get user info for mention display"""
    from sqlmodel import select
    user = (await db.exec(select(User).where(User.id == user_id))).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserMentionInfo(
        id=user.id,
        full_name=user.full_name,
        username=user.email.split('@')[0] if user.email else None,  # Temporary username
        profile_image_url=f"{user.profile_image_url}?v={int(user.profile_image_uploaded_at.timestamp())}" if user.profile_image_url and user.profile_image_uploaded_at else user.profile_image_url,
        job_title=user.job_title,
        company=user.company
    )