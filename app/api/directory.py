"""
Professional directory endpoints
(Search & Filtering) and (User Directory)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Union
from sqlmodel import select, and_, or_

from app.db.database import get_db
from app.models.user import User
from app.models.post import Post
from app.schemas.directory import DirectorySearchParams, UserDirectoryItem, LocationFilter
from app.schemas.post import PostRead
from app.core.security import get_current_user
from app.crud.user import search_users
from app.crud.post import search_jobs_by_criteria

router = APIRouter(prefix="/directory", tags=["directory"])

@router.get("/", response_model=List[Union[UserDirectoryItem, PostRead]])
async def search_directory(
    params: DirectorySearchParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Search professionals and job postings with advanced filtering.
    """
    # location filter if provided
    location_str = None
    if params.location:
        loc_parts = []
        if params.location.country:
            loc_parts.append(params.location.country)
        if params.location.state:
            loc_parts.append(params.location.state)
        location_str = ", ".join(loc_parts) if loc_parts else None

    # Convert experience to string as it's enum
    experience_str = params.experience
    if hasattr(params.experience, 'value'):
        experience_str = params.experience.value

    # Search for users
    users = await search_users(
        db,
        query=params.q,
        industry=params.industry.value if params.industry else None,
        experience=experience_str,
        location=location_str,
        skills=params.skill,
        job_title=params.job_title,
        recruiter_only=params.recruiter_only,
        hide_hidden=True
    )

    # Search for job postings
    jobs = await search_jobs_by_criteria(
        db,
        skill=params.skill,
        location=location_str,
        experience=experience_str,
        job_title=params.job_title
    )

    # Combine and transform results
    return transform_results(users, jobs)

def transform_results(users: List[User], jobs: List[Post]) -> List[Union[UserDirectoryItem, PostRead]]:
    """Transform database results to response models"""
    user_results = [
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

    job_results = [
        PostRead.from_orm(job)
        for job in jobs
    ]

    return user_results + job_results
