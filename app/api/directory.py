"""
Professional directory endpoints
(Search & Filtering) and (User Directory)
"""

import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Union

from app.db.database import get_db
from app.models.user import User
from app.models.post import Post
from app.schemas.directory import DirectorySearchParams, UserDirectoryItem
from app.schemas.post import PostRead
from app.core.security import get_current_user
from app.crud.user import search_users
from app.crud.post import search_jobs_by_criteria
from app.core.exceptions import CustomHTTPException
from app.core.error_codes import (
    DIRECTORY_SEARCH_ERROR,
    INVALID_SEARCH_PARAMS,
    UNAUTHORIZED_ACCESS
)

router = APIRouter(prefix="/directory", tags=["directory"])


@router.post("/", response_model=List[Union[UserDirectoryItem, PostRead]])
async def search_directory(
    params: DirectorySearchParams,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Search professionals and job postings with advanced filtering.
    """
    try:
        # 1) Active user check
        if not current_user.is_active:
            raise CustomHTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated",
                error_code=UNAUTHORIZED_ACCESS
            )

        # 2) At least one filter required
        if not any([
            params.q,
            params.industry,
            params.experience,
            params.location,
            params.skill,
            params.job_title
        ]):
            raise CustomHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one search parameter is required",
                error_code=INVALID_SEARCH_PARAMS
            )

        # 3) Build location string
        location_str: Optional[str] = None
        if params.location:
            parts = []
            if params.location.country:
                parts.append(params.location.country)
            if params.location.state:
                parts.append(params.location.state)
            if parts:
                location_str = ", ".join(parts)

        # 4) Pull enum-fields as plain strings
        industry_str: Optional[str]  = params.industry
        experience_str: Optional[str] = params.experience
        job_title_str: Optional[str]  = params.job_title

        # 5) Wrap single skill into list if your CRUD expects list
        skills_arg = [params.skill] if params.skill else None

        # 6) Run user search
        users = await search_users(
            db,
            query=params.q,
            industry=industry_str,
            experience=experience_str,
            location=location_str,
            skills=skills_arg,
            job_title=job_title_str,
            recruiter_only=params.recruiter_only,
            hide_hidden=True
        )

        # 7) Run job-post search across ALL users (no follow filter)
        jobs = await search_jobs_by_criteria(
            db,
            skill=skills_arg,
            location=location_str,
            experience=experience_str,
            job_title=job_title_str
        )

        # 8) Combine + return
        return transform_results(users, jobs)

    except CustomHTTPException:
        raise
    except Exception:
        logging.exception("directory.search_directory failed")
        raise CustomHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error searching directory",
            error_code=DIRECTORY_SEARCH_ERROR
        )


def transform_results(
    users: List[User],
    jobs: List[Post]
) -> List[Union[UserDirectoryItem, PostRead]]:
    """Transform database results into the response schemas."""
    try:
        user_results = [
            UserDirectoryItem(
                id=user.id,
                full_name=user.full_name,
                job_title=(user.job_title if not getattr(user, "hide_profile", False) else None),
                company=(user.company if not getattr(user, "hide_profile", False) else None),
                industry=(user.industry.value if not getattr(user, "hide_profile", False) else None),
                is_recruiter=user.recruiter_tag
            )
            for user in users
        ]

        job_results = [PostRead.from_orm(job) for job in jobs]
        return user_results + job_results

    except Exception:
        logging.exception("directory.transform_results failed")
        raise CustomHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error transforming results",
            error_code=DIRECTORY_SEARCH_ERROR
        )

