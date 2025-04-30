"""
Admin endpoints covering all requirements:
- User management (activate/deactivate, edit profiles)
- Content moderation (posts, profiles)
- Dropdown customization
- Admin metrics
- System configuration
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
from app.db.database import get_db
from app.models.user import User
from app.schemas.user import UserRead, UserUpdate, UserDirectoryItem
from app.schemas.post import PostRead
from app.core.security import get_current_active_admin
from app.schemas.enums import Industry, ExperienceLevel, JobTitle
from app.crud import (
    user as crud_user,
    post as crud_post,
    skill as crud_skill
)

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_active_admin)]
)


class DropdownUpdate(BaseModel):
    job_titles: Optional[List[JobTitle]] = None
    industries: Optional[List[Industry]] = None
    skills: Optional[List[str]] = None
    experience_levels: Optional[List[ExperienceLevel]] = None

class AdminMetrics(BaseModel):
    total_users: int
    active_users: int
    new_users_24h: int
    recruiters: int
    total_posts: int
    active_posts: int
    profile_completion_rate: float
    recent_signups: List[UserRead]
    recent_posts: List[PostRead]

class UserSearchFilters(BaseModel):
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    recruiter_tag: Optional[bool] = None
    industry: Optional[Industry] = None
    experience_level: Optional[ExperienceLevel] = None

class BulkActionRequest(BaseModel):
    user_ids: List[UUID]
    action: str  # "activate", "deactivate", "verify"


@router.get("/users", response_model=List[UserDirectoryItem])
async def admin_list_users(
    filters: UserSearchFilters = Depends(),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """List users with advanced filters """
    users = await crud_user.get_filtered_users(
        db,
        is_active=filters.is_active,
        is_verified=filters.is_verified,
        recruiter_tag=filters.recruiter_tag,
        industry=filters.industry,
        experience_level=filters.experience_level,
        skip=skip,
        limit=limit
    )
    return users

@router.post("/users/bulk-actions", response_model=Dict[str, int])
async def bulk_user_actions(
    request: BulkActionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Bulk user actions (activate/deactivate/verify)"""
    return await crud_user.bulk_user_actions(
        db,
        user_ids=request.user_ids,
        action=request.action
    )

@router.post("/users/{user_id}/deactivate", response_model=UserRead)
async def deactivate_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Deactivate a user account"""
    user = await crud_user.get(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return await crud_user.update(db, db_obj=user, obj_in={"is_active": False})

@router.post("/users/{user_id}/activate", response_model=UserRead)
async def activate_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Reactivate a user account"""
    user = await crud_user.get(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return await crud_user.update(db, db_obj=user, obj_in={"is_active": True})

@router.put("/users/{user_id}", response_model=UserRead)
async def admin_update_user(
    user_id: UUID,
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Admin edit user profile """
    user = await crud_user.get(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return await crud_user.update(db, db_obj=user, obj_in=user_update)


@router.get("/posts", response_model=List[PostRead])
async def admin_list_posts(
    is_active: Optional[bool] = None,
    industry: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """List posts with moderation filters"""
    posts = await crud_post.get_filtered_posts(
        db,
        is_active=is_active,
        industry=industry,
        skip=skip,
        limit=limit
    )
    return posts

@router.patch("/posts/{post_id}/visibility", response_model=PostRead)
async def toggle_post_visibility(
    post_id: UUID,
    is_active: bool = Body(..., embed=True),
    db: AsyncSession = Depends(get_db)
):
    """Toggle post visibility """
    post = await crud_post.get(db, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return await crud_post.update(db, db_obj=post, obj_in={"is_active": is_active})

@router.delete("/posts/{post_id}")
async def admin_delete_post(
    post_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Permanently delete a post"""
    post = await crud_post.get(db, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    await crud_post.remove(db, id=post_id)
    return {"message": "Post deleted successfully"}


@router.get("/dropdowns", response_model=DropdownUpdate)
async def get_dropdown_options(db: AsyncSession = Depends(get_db)):
    """Get current dropdown options using enums and skill model"""
    return {
        "industries": Industry.list(),  # Enum-based
        "experience_levels": ExperienceLevel.list(),  # Enum-based
        "job_titles": JobTitle.list(),  # Enum-based
        "skills": await crud_skill.get_all(db)  # From model
    }


@router.get("/metrics", response_model=AdminMetrics)
async def get_admin_metrics(db: AsyncSession = Depends(get_db)):
    """Get system metrics """
    users = await crud_user.get_multi(db)
    posts = await crud_post.get_multi(db)
    now = datetime.utcnow()
    
    return {
        "total_users": len(users),
        "active_users": sum(1 for u in users if u.is_active),
        "new_users_24h": sum(1 for u in users if now - u.created_at < timedelta(days=1)),
        "recruiters": sum(1 for u in users if u.recruiter_tag),
        "total_posts": len(posts),
        "active_posts": sum(1 for p in posts if p.is_active),
        "profile_completion_rate": calculate_completion_rate(users),
        "recent_signups": sorted(
            [u for u in users if u.is_active],
            key=lambda x: x.created_at,
            reverse=True
        )[:5],
        "recent_posts": sorted(
            [p for p in posts if p.is_active],
            key=lambda x: x.created_at,
            reverse=True
        )[:5]
    }

def calculate_completion_rate(users: List[User]) -> float:
    """Calculate average profile completion rate"""
    if not users:
        return 0.0
    total = sum(user.profile_completion for user in users if hasattr(user, 'profile_completion'))
    return round(total / len(users), 2)
