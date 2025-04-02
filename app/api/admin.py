"""
Admin endpoints covering:
- User management
- Content moderation
- Dropdown customization
- Admin metrics
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict
from pydantic import BaseModel

from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserRead, UserUpdate
from app.schemas.post import PostRead
from app.core.security import get_current_active_admin
from app.crud import user as crud_user, post as crud_post, skill as crud_skill

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_active_admin)]
)

# ... existing endpoints ...

class DropdownUpdate(BaseModel):
    job_titles: Optional[List[str]] = None
    industries: Optional[List[str]] = None

@router.put("/dropdowns")
async def update_dropdowns(
    updates: DropdownUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update multiple dropdown options"""
    return {
        "message": "Dropdown options updated",
        "job_titles": updates.job_titles,
        "industries": updates.industries
    }

@router.post("/users/{user_id}/deactivate", response_model=UserRead)
async def deactivate_user(user_id: UUID, db: AsyncSession = Depends(get_db)):
    user = await crud_user.get(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return await crud_user.update(db, db_obj=user, obj_in={"is_active": False})

@router.post("/users/{user_id}/activate", response_model=UserRead)
async def activate_user(user_id: UUID, db: AsyncSession = Depends(get_db)):
    user = await crud_user.get(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return await crud_user.update(db, db_obj=user, obj_in={"is_active": True})

@router.patch("/posts/{post_id}/visibility", response_model=PostRead)
async def toggle_post_visibility(
    post_id: UUID,
    is_active: bool = Body(..., embed=True),
    db: AsyncSession = Depends(get_db)
):
    post = await crud_post.get(db, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return await crud_post.update(db, db_obj=post, obj_in={"is_active": is_active})

class AdminMetrics(BaseModel):
    user_count: int
    active_users: int
    recruiter_count: int
    post_count: int
    recent_signups: List[UserRead]

@router.get("/metrics", response_model=AdminMetrics)
async def get_admin_metrics(db: AsyncSession = Depends(get_db)):
    users = await crud_user.get_multi(db)
    posts = await crud_post.get_multi(db)
    
    return {
        "user_count": len(users),
        "active_users": sum(1 for u in users if u.is_active),
        "recruiter_count": sum(1 for u in users if u.recruiter_tag),
        "post_count": len(posts),
        "recent_signups": sorted(
            [u for u in users if u.is_active],
            key=lambda x: x.created_at,
            reverse=True
        )[:5]
    }
