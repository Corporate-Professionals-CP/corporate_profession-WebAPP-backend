"""
Professional directory endpoints
(Search & Filtering) and (User Directory)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from sqlmodel import select, and_, or_

from app.db.database import get_db
from app.models.user import User
from app.schemas.directory import DirectorySearchParams, UserDirectoryItem, LocationFilter
from app.core.security import get_current_user
from app.crud.user import search_users  # Reuse optimized search

router = APIRouter(prefix="/directory", tags=["directory"])

@router.get("/", response_model=List[UserDirectoryItem])
async def search_directory(
    params: DirectorySearchParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Search professionals with advanced filtering
    Requirements:
    - Search by name, job title, company, or industry
    - Filter by industry, role, experience, location, skills
    - Hide profile details when privacy enabled
    - Show recruiter tag
    """
    # Build location filter if provided
    location_str = None
    if params.location:
        loc_parts = []
        if params.location.country:
            loc_parts.append(params.location.country)
        if params.location.state:
            loc_parts.append(params.location.state)
        location_str = ", ".join(loc_parts) if loc_parts else None

    # Use optimized CRUD search function
    users = await search_users(
        db,
        query=params.q,
        industry=params.industry,
        experience=params.experience,
        location=location_str,
        skill=params.skill,
        recruiter_only=params.recruiter_only,
        hide_hidden=True  # Respect privacy settings
    )

    if not users:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No professionals found matching your criteria"
        )

    # Transform to directory items respecting privacy
    return [
        UserDirectoryItem(
            id=user.id,
            full_name=user.full_name,
            job_title=user.job_title if not user.hide_profile else None,
            company=user.company if not user.hide_profile else None,
            industry=user.industry.value if not user.hide_profile else None,
            is_recruiter=user.recruiter_tag
        )
        for user in users
    ]
