"""
Admin endpoints covering all requirements:
- User management (activate/deactivate, edit profiles)
- Enhanced user management (detailed search, activity tracking, bulk actions)
- Content moderation (posts, profiles)
- Dropdown customization
- Admin metrics
- System configuration
"""

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Optional, Any
from pydantic import BaseModel
from datetime import datetime, timedelta
from app.db.database import get_db
from app.models.user import User
from app.models.post import Post
from app.models.connection import Connection
from app.schemas.user import UserRead, UserUpdate, UserDirectoryItem
from app.schemas.post import PostRead, PostUpdate
from app.schemas.skill import SkillRead
from app.core.security import get_current_active_admin
from app.schemas.enums import Industry, ExperienceLevel, PostVisibility
from app.crud import (
    user as crud_user,
    post as crud_post,
    skill as crud_skill,
    job_title as crud_job_title
)
from app.core.exceptions import CustomHTTPException
from app.core.error_codes import (
    ADMIN_USER_NOT_FOUND,
    ADMIN_POST_NOT_FOUND,
    ADMIN_UPDATE_ERROR,
    ADMIN_DELETE_ERROR,
    ADMIN_BULK_ACTION_ERROR,
    ADMIN_METRICS_ERROR,
    ADMIN_DROPDOWN_ERROR
)
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.exc import IntegrityError
router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_active_admin)]
)


class DropdownUpdate(BaseModel):
    job_titles: Optional[List[str]] = None
    industries: Optional[List[Industry]] = None
    skills: Optional[List[SkillRead]] = None
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

# Enhanced User Management Models
class UserActivitySummary(BaseModel):
    total_posts: int
    total_connections: int
    last_login: Optional[datetime]
    login_frequency: float  # logins per week
    account_age_days: int
    warning_count: int
    is_suspended: bool

class EnhancedUserDetails(BaseModel):
    user: UserRead
    activity_summary: UserActivitySummary
    recent_activities: List[Dict[str, Any]]
    admin_notes: Optional[str]

class EnhancedUserSearchRequest(BaseModel):
    # Basic filters (existing)
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    recruiter_tag: Optional[bool] = None
    industry: Optional[Industry] = None
    experience_level: Optional[ExperienceLevel] = None
    
    # Enhanced filters (new)
    name: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    signup_date_from: Optional[datetime] = None
    signup_date_to: Optional[datetime] = None
    has_warnings: Optional[bool] = None

class EnhancedBulkAction(BaseModel):
    user_ids: List[UUID]
    action: str  # 'suspend', 'unsuspend', 'verify', 'unverify', 'add_warning'
    reason: Optional[str] = None

class AdminNoteUpdate(BaseModel):
    notes: str

class UserExportData(BaseModel):
    users: List[UserRead]
    total_count: int
    export_date: datetime


@router.get("/users", response_model=List[UserDirectoryItem])
async def admin_list_users(
    filters: UserSearchFilters = Depends(),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """List users with advanced filters """
    try:
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
        if not users:
            raise CustomHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No users found matching criteria",
                error_code=ADMIN_USER_NOT_FOUND
            )
        return users
    except Exception as e:
        raise CustomHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No users found matching criteria",
            error_code=ADMIN_USER_NOT_FOUND
        )

@router.post("/users/bulk-actions", response_model=Dict[str, int])
async def bulk_user_actions(
    request: BulkActionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Bulk user actions with custom error handling"""
    try:
        result = await crud_user.bulk_user_actions(
            db,
            user_ids=request.user_ids,
            action=request.action
        )
        if not result:
            raise CustomHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No users were updated",
                error_code=ADMIN_BULK_ACTION_ERROR
            )
        return result
    except Exception as e:
        raise CustomHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=" bulk actions failed, no user were updated",
            error_code=ADMIN_BULK_ACTION_ERROR
        )


@router.post("/users/{user_id}/deactivate", response_model=UserRead)
async def deactivate_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    """Deactivate user with custom error handling"""
    try:
        user = await crud_user.update_user_status(
            session=db,
            user_id=user_id,
            is_active=False,
            current_user=current_admin
        )
        if not user:
            raise CustomHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
                error_code=ADMIN_USER_NOT_FOUND
            )
        return user
    except Exception as e:
        raise CustomHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Error deactivating user, user does not exist",
            error_code=ADMIN_UPDATE_ERROR
        )


@router.post("/users/{user_id}/activate", response_model=UserRead)
async def activate_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    """Activate user with custom error handling"""
    try:
        user = await crud_user.update_user_status(
            session=db,
            user_id=user_id,
            is_active=True,
            current_user=current_admin
        )
        if not user:
            raise CustomHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
                error_code=ADMIN_USER_NOT_FOUND
            )
        return user
    except Exception as e:
        raise CustomHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Error activating user, user does not exist",
            error_code=ADMIN_UPDATE_ERROR
        )


@router.put("/users/{user_id}", response_model=UserRead)
async def admin_update_user(
    user_id: UUID,
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin),
):
    # Fetch user (including inactive ones)
    user = await crud_user.get_user_for_update(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Apply updates directly (skip all validations)
    update_data = user_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    try:
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")

@router.get("/posts/", response_model=List[PostRead])
async def admin_list_posts(
    is_active: Optional[bool] = Query(None),
    industry: Optional[Industry] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin),
):
    return await crud_post.get_filtered_posts(
        session=db,
        is_active=is_active,
        industry=industry,
        offset=offset,
        limit=limit
    )

@router.patch("/posts/{post_id}/visibility", response_model=PostRead)
async def admin_update_post_visibility(
    post_id: UUID,
    visibility: PostVisibility = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    post = await crud_post.get_post_by_id_admin(db, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    post.visibility = visibility.value
    post.updated_at = datetime.utcnow()
    
    try:
        await db.commit()
        await db.refresh(post)
        return post
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating post: {str(e)}")


@router.delete("/posts/{post_id}", status_code=204)
async def admin_delete_post(
    post_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    """Admin-only post deletion (soft delete)"""
    post = await crud_post.get_post_by_id_admin(db, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    try:
        # Perform soft delete
        post.deleted = True
        post.updated_at = datetime.utcnow()
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting post: {str(e)}")


@router.get("/dropdowns", response_model=DropdownUpdate)
async def get_dropdown_options(db: AsyncSession = Depends(get_db)):
    """Get current dropdown options using enums and skill model"""
    return {
        "industries": Industry.list(),  # Enum-based
        "experience_levels": ExperienceLevel.list(), # Enum-based
        "job_titles": [jt.name for jt in await crud_job_title.get_all(db)],  # from db
        "skills": await crud_skill.get_multi(db)  # From model
    }

@router.get("/metrics", response_model=AdminMetrics)
async def get_admin_metrics(db: AsyncSession = Depends(get_db)):
    """Get system metrics"""
    users = await crud_user.get_multi(db, include_inactive=True)
    
    posts = await crud_post.get_multi(db, include_inactive=True)
    
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

# ENHANCED USER MANAGEMENT ENDPOINTS

@router.get("/users/enhanced-search", response_model=List[UserRead])
async def enhanced_user_search(
    search: EnhancedUserSearchRequest = Depends(),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_active_admin)
):
    """Enhanced user search with multiple criteria including name, email, company, signup dates"""
    
    # Build dynamic query
    query = select(User)
    conditions = []
    
    # Basic filters (existing functionality)
    if search.is_active is not None:
        conditions.append(User.is_active == search.is_active)
    if search.is_verified is not None:
        conditions.append(User.is_verified == search.is_verified)
    if search.recruiter_tag is not None:
        conditions.append(User.recruiter_tag == search.recruiter_tag)
    if search.industry:
        conditions.append(User.industry == search.industry)
    
    # Enhanced filters (new functionality)
    if search.name:
        conditions.append(User.full_name.ilike(f"%{search.name}%"))
    if search.email:
        conditions.append(User.email.ilike(f"%{search.email}%"))
    if search.company:
        conditions.append(User.company.ilike(f"%{search.company}%"))
    if search.signup_date_from:
        conditions.append(User.created_at >= search.signup_date_from)
    if search.signup_date_to:
        conditions.append(User.created_at <= search.signup_date_to)
    if search.has_warnings is not None:
        if search.has_warnings:
            conditions.append(User.warning_count > 0)
        else:
            conditions.append(or_(User.warning_count == 0, User.warning_count.is_(None)))
    
    if conditions:
        query = query.where(and_(*conditions))
    
    query = query.offset(skip).limit(limit).order_by(desc(User.created_at))
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return users


@router.get("/users/{user_id}/details", response_model=EnhancedUserDetails)
async def get_enhanced_user_details(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_active_admin)
):
    """Get detailed user information with activity summary and recent activities"""
    
    # Get user
    user_query = select(User).where(User.id == str(user_id))
    user_result = await db.execute(user_query)
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise CustomHTTPException(
            status_code=404,
            detail="User not found",
            error_code=ADMIN_USER_NOT_FOUND
        )
    
    # Get activity summary
    posts_count_query = select(func.count(Post.id)).where(Post.user_id == str(user_id))
    posts_result = await db.execute(posts_count_query)
    total_posts = posts_result.scalar() or 0
    
    connections_count_query = select(func.count(Connection.id)).where(
        or_(Connection.sender_id == str(user_id), Connection.receiver_id == str(user_id))
    )
    connections_result = await db.execute(connections_count_query)
    total_connections = connections_result.scalar() or 0
    
    # Calculate login frequency (logins per week)
    account_age = (datetime.utcnow() - user.created_at).days
    login_frequency = (getattr(user, 'login_count', 0) * 7) / max(account_age, 1) if account_age > 0 else 0
    
    # Get detailed profile completion
    try:
        from app.crud.user import get_profile_completion
        profile_completion_data = await get_profile_completion(db, user_id)
    except Exception as e:
        # Fallback to basic completion if detailed fails
        profile_completion_data = {
            "completion_percentage": user.profile_completion,
            "missing_fields": [],
            "sections": {}
        }
    
    # Mock recent activities (will be implementing UserActivityLog later)
    recent_activities = [
        {
            "type": "login",
            "description": "User logged in",
            "date": getattr(user, 'last_login_at', user.created_at),
            "metadata": {"login_count": getattr(user, 'login_count', 0)}
        },
        {
            "type": "profile_update",
            "description": "Profile updated",
            "date": user.updated_at,
            "metadata": {
                "completion_percentage": profile_completion_data.completion_percentage if hasattr(profile_completion_data, 'completion_percentage') else user.profile_completion,
                "missing_fields_count": len(profile_completion_data.missing_fields) if hasattr(profile_completion_data, 'missing_fields') else 0
            }
        }
    ]
    
    activity_summary = UserActivitySummary(
        total_posts=total_posts,
        total_connections=total_connections,
        last_login=getattr(user, 'last_login_at', None),
        login_frequency=round(login_frequency, 2),
        account_age_days=account_age,
        warning_count=getattr(user, 'warning_count', 0),
        is_suspended=getattr(user, 'suspended_at', None) is not None
    )
    
    return EnhancedUserDetails(
        user=user,
        activity_summary=activity_summary,
        recent_activities=recent_activities,
        admin_notes=getattr(user, 'notes', None)
    )


@router.post("/users/enhanced-bulk-actions", response_model=Dict[str, Any])
async def enhanced_bulk_actions(
    action_request: EnhancedBulkAction,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_active_admin)
):
    """Enhanced bulk actions with detailed logging and more action types"""
    
    # Get users
    users_query = select(User).where(User.id.in_([str(uid) for uid in action_request.user_ids]))
    users_result = await db.execute(users_query)
    users = users_result.scalars().all()
    
    if not users:
        raise CustomHTTPException(
            status_code=404,
            detail="No users found",
            error_code=ADMIN_USER_NOT_FOUND
        )
    
    updated_count = 0
    action_log = []
    
    for user in users:
        original_state = {
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "warning_count": getattr(user, 'warning_count', 0)
        }
        
        if action_request.action == "suspend":
            user.is_active = False
            if hasattr(user, 'suspended_at'):
                user.suspended_at = datetime.utcnow()
            if hasattr(user, 'suspended_by'):
                user.suspended_by = str(admin.id)
            if hasattr(user, 'suspension_reason'):
                user.suspension_reason = action_request.reason
                
        elif action_request.action == "unsuspend":
            user.is_active = True
            if hasattr(user, 'suspended_at'):
                user.suspended_at = None
            if hasattr(user, 'suspended_by'):
                user.suspended_by = None
            if hasattr(user, 'suspension_reason'):
                user.suspension_reason = None
                
        elif action_request.action == "verify":
            user.is_verified = True
            
        elif action_request.action == "unverify":
            user.is_verified = False
            
        elif action_request.action == "add_warning":
            if hasattr(user, 'warning_count'):
                user.warning_count = getattr(user, 'warning_count', 0) + 1
        
        # Log the action
        action_log.append({
            "user_id": str(user.id),
            "user_email": user.email,
            "action": action_request.action,
            "reason": action_request.reason,
            "original_state": original_state,
            "performed_by": admin.email,
            "timestamp": datetime.utcnow()
        })
        
        updated_count += 1
    
    await db.commit()
    
    return {
        "updated_count": updated_count,
        "action": action_request.action,
        "reason": action_request.reason,
        "performed_by": admin.email,
        "timestamp": datetime.utcnow(),
        "action_log": action_log
    }


@router.put("/users/{user_id}/admin-notes", response_model=Dict[str, str])
async def update_admin_notes(
    user_id: UUID,
    note_update: AdminNoteUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_active_admin)
):
    """Update admin notes for a user"""
    
    user_query = select(User).where(User.id == str(user_id))
    user_result = await db.execute(user_query)
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise CustomHTTPException(
            status_code=404,
            detail="User not found",
            error_code=ADMIN_USER_NOT_FOUND
        )
    
    # Add notes field if it doesn't exist (graceful handling)
    if hasattr(user, 'notes'):
        user.notes = note_update.notes
    user.updated_at = datetime.utcnow()
    
    await db.commit()
    
    return {
        "message": "Notes updated successfully",
        "updated_by": admin.email,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/users/export", response_model=UserExportData)
async def export_users(
    search: EnhancedUserSearchRequest = Depends(),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_active_admin)
):
    """Export user data based on search criteria (CSV/Excel format preparation)"""
    
    # Reuse the enhanced search logic
    query = select(User)
    conditions = []
    
    if search.is_active is not None:
        conditions.append(User.is_active == search.is_active)
    if search.is_verified is not None:
        conditions.append(User.is_verified == search.is_verified)
    if search.recruiter_tag is not None:
        conditions.append(User.recruiter_tag == search.recruiter_tag)
    if search.name:
        conditions.append(User.full_name.ilike(f"%{search.name}%"))
    if search.email:
        conditions.append(User.email.ilike(f"%{search.email}%"))
    if search.company:
        conditions.append(User.company.ilike(f"%{search.company}%"))
    if search.signup_date_from:
        conditions.append(User.created_at >= search.signup_date_from)
    if search.signup_date_to:
        conditions.append(User.created_at <= search.signup_date_to)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    # Limit export to reasonable size
    query = query.limit(10000).order_by(desc(User.created_at))
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return UserExportData(
        users=users,
        total_count=len(users),
        export_date=datetime.utcnow()
    )
