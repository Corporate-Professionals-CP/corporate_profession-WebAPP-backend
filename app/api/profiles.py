"""
profile endpoints implementation
- Profile viewing with privacy controls
- Profile management
- CV upload handling
"""

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Union, Optional
import shutil
import os
from datetime import timedelta
from app.db.database import get_db
from app.models.user import User
from app.schemas.user import UserRead, UserPublic, UserUpdate, UserProfileCompletion
from app.core.security import get_current_active_user, get_current_active_admin
from app.crud.user import (
    get_user_by_id,
    update_user,
    upload_user_cv,
    get_profile_completion
)
from google.cloud.exceptions import GoogleCloudError
from urllib.parse import urlparse
from app.core.config import settings

from app.utils.file_handling import save_uploaded_file, delete_user_file
from fastapi.responses import FileResponse
#from app.utils.file_handling import save_uploaded_file, delete_user_file, bucket
from fastapi.responses import FileResponse, RedirectResponse

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/profiles", tags=["profiles"])

@router.get("/me", response_model=UserRead)
async def get_own_profile(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current user's full profile (always visible to owner)
    """
    return current_user

@router.get("/{user_id}", response_model=Union[UserRead, UserPublic])
async def get_profile(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get user profile with privacy control
    - Full profile for owner/admins
    - Public view respects hide_profile
    - Recruiter tag visibility
    - Minimal info when profile hidden (only name + recruiter tag)
    """
    # Admin or owner can see full profile regardless
    is_owner_or_admin = str(current_user.id) == str(user_id) or current_user.is_admin
    
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Return full profile if owner/admin or profile not hidden
    if is_owner_or_admin or not user.hide_profile:
        return user
    
    # Return minimal public profile
    return UserPublic(
        id=user.id,
        full_name=user.full_name,
        recruiter_tag=user.recruiter_tag
    )

@router.get("/{user_id}/completion", response_model=UserProfileCompletion)
async def get_profile_completion_status(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get profile completion percentage
    Profile completion status
    """
    # Only allow users to check their own completion unless admin
    if str(current_user.id) != str(user_id) and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only check your own profile completion"
        )

    completion = await get_profile_completion(db, user_id)
    return completion

@router.put("/{user_id}", response_model=UserRead)
async def update_profile(
    user_id: UUID,
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update user profile
    - Only owner/admin can update
    - Supports recruiter tag toggle
    - Supports hide profile toggle
    - Validates required fields
    """
    # Verify ownership or admin rights
    if str(current_user.id) != str(user_id) and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this profile"
        )

    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )



    # Special handling for admin-only fields
    if not current_user.is_admin:
        if user_update.is_admin is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        if user_update.is_active is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot modify account status"
            )
    # Validate required fields
    # Conditionally require profile fields for regular professionals only
    is_professional = not user.recruiter_tag and not current_user.is_admin
    if is_professional:
        required_fields = ["full_name", "email", "job_title", "industry", "location", "years_of_experience"]
        for field in required_fields:
            if getattr(user_update, field) is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{field} is required for professional users"
                )


    updated_user = await update_user(db, user_id, user_update, current_user)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )
    updated_user.update_profile_completion()

    await db.commit()

    return updated_user

@router.post("/{user_id}/cv", response_model=UserRead)
async def upload_cv(
    user_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload or update user CV to Google Cloud Storage
    - Only owner/admin can upload
    - Supports PDF/DOCX files
    - Stores in GCS with proper access control
    - Updates user record with GCS URL
    """
    # Verify ownership or admin rights
    if str(current_user.id) != str(user_id) and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this profile"
        )

    try:
        # Save file to GCS and get the URL
        cv_url = await save_uploaded_file(file, str(user_id))

        # Update user record with the new CV URL
        user = await get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        user.cv_url = cv_url
        await db.commit()
        await db.refresh(user)

        return user

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload CV to GCS: {str(e)}"
        )

@router.delete("/{user_id}/cv", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cv(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Remove user CV from Google Cloud Storage
    - Deletes file from GCS bucket
    - Clears CV URL from user record
    """
    # Verify ownership or admin rights
    if str(current_user.id) != str(user_id) and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this profile"
        )

    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not user.cv_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No CV found to delete"
        )

    try:
        # Delete from GCS
        success = await delete_user_file(user.cv_url)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete CV from storage"
            )

        # Clear CV URL from user record
        user.cv_url = None
        await db.commit()

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete CV: {str(e)}"
        )


@router.get("/{user_id}/cv")
async def download_cv(
    user_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    user = await get_user_by_id(db, user_id)
    if not user or not user.cv_url:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CV not found")

    try:
        # Validate URL structure
        parsed_url = urlparse(user.cv_url)
        if not parsed_url.netloc.endswith('storage.googleapis.com'):
            raise ValueError("Invalid GCS URL format")

        # Extract bucket name and blob path from URL
        path_parts = parsed_url.path.lstrip('/').split('/')
        if len(path_parts) < 2:
            raise ValueError("Invalid GCS URL path structure")

        bucket_name = path_parts[0]
        blob_path = '/'.join(path_parts[1:]).split('?')[0]

        if bucket_name != settings.GCS_BUCKET_NAME:
            raise ValueError("Bucket name mismatch")

        # Get blob reference
        blob = bucket.blob(blob_path)

        if not blob.exists():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "CV file not found in storage")

        # Generate fresh signed URL with 5 minute expiration
        new_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=5),
            method="GET"
        )

        return RedirectResponse(url=new_url)

    except ValueError as e:
        logger.error(f"URL validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid CV URL format"
        )
    except GoogleCloudError as e:
        logger.error(f"GCS API error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service unavailable"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate download URL"
        )

