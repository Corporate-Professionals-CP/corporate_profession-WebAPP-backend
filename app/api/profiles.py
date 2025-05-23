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
    delete_user_cv,
    get_profile_completion,
    upload_user_profile_image,
    delete_user_profile_image
)
from google.cloud.exceptions import GoogleCloudError
from urllib.parse import urlparse
from app.core.config import settings
from fastapi.responses import FileResponse

from app.utils.file_handling import save_uploaded_file, delete_user_file, bucket
from fastapi.responses import FileResponse, RedirectResponse
from app.core.exceptions import CustomHTTPException
from app.core.error_codes import (
    USER_NOT_FOUND,
    NOT_AUTHORIZED,
    CV_UPLOAD_FAILED,
    CV_NOT_FOUND,
    INVALID_CV_URL,
    GCS_UNAVAILABLE,
    CV_DELETE_FAILED,
    PROFILE_UPDATE_FAILED,
    PROFILE_COMPLETION_FORBIDDEN,
    REQUIRED_FIELD_MISSING,
    ADMIN_PRIVILEGE_REQUIRED
)
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
        raise CustomHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
            error_code=USER_NOT_FOUND,
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
        raise CustomHTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only check your own profile completion",
            error_code=PROFILE_COMPLETION_FORBIDDEN,
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
        raise CustomHTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this profile",
            error_code=NOT_AUTHORIZED,
        )

    user = await get_user_by_id(db, user_id)
    if not user:
        raise CustomHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
            error_code=USER_NOT_FOUND,
        )



    # Special handling for admin-only fields
    if not current_user.is_admin:
        if user_update.is_admin is not None:
            raise CustomHTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required to perform some of this updating operation",
                error_code=ADMIN_PRIVILEGE_REQUIRED,
            )
        if user_update.is_active is not None:
            raise CustomHTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot modify account status",
                error_code=ADMIN_PRIVILEGE_REQUIRED,
            )
    # Validate required fields
    # Conditionally require profile fields for regular professionals only
    is_professional = not user.recruiter_tag and not current_user.is_admin
    if is_professional:
        required_fields = ["full_name", "email", "job_title", "industry", "location", "years_of_experience"]
        for field in required_fields:
            if getattr(user_update, field) is None:
                raise CustomHTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{field} is required for professional users",
                    error_code=REQUIRED_FIELD_MISSING,
                )


    updated_user = await update_user(db, user_id, user_update, current_user)
    if not updated_user:
        raise CustomHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile",
            error_code=PROFILE_UPDATE_FAILED,
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
        raise CustomHTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this profile",
            error_code=NOT_AUTHORIZED,
        )

    try:
        # Save file to GCS and get the URL
        cv_url = await save_uploaded_file(file, str(user_id))

        # Update user record with the new CV URL
        user = await get_user_by_id(db, user_id)
        if not user:
            raise CustomHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
                error_code=USER_NOT_FOUND,
            )

        user.cv_url = cv_url
        await db.commit()
        await db.refresh(user)

        return user

    except HTTPException as he:
        raise he
    except Exception as e:
        raise CustomHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload CV to GCS: {str(e)}",
            error_code=CV_UPLOAD_FAILED,
        )

@router.delete("/{user_id}/cv", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cv(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if str(current_user.id) != str(user_id) and not current_user.is_admin:
        raise CustomHTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this profile",
            error_code=NOT_AUTHORIZED,
        )

    try:
        await delete_user_cv(db, user_id)
    except HTTPException:
        raise
    except Exception as e:
        raise CustomHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete CV: {str(e)}",
            error_code=CV_DELETE_FAILED,
        )

@router.get("/{user_id}/cv")
async def download_cv(
    user_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    user = await get_user_by_id(db, user_id)
    if not user or not user.cv_url:
        raise CustomHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV not found",
            error_code=CV_NOT_FOUND,
        )

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
            raise CustomHTTPException(status.HTTP_404_NOT_FOUND, "CV file not found in storage")

        # Generate fresh signed URL with 5 minute expiration
        new_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=5),
            method="GET"
        )

        return RedirectResponse(url=new_url)

    except ValueError as e:
        logger.error(f"URL validation error: {str(e)}")
        raise CustomHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid CV URL format",
            error_code=INVALID_CV_URL,
        )
    except GoogleCloudError as e:
        logger.error(f"GCS API error: {str(e)}")
        raise CustomHTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service unavailable",
            error_code=GCS_UNAVAILABLE,
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise CustomHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate download URL",
            error_code=GCS_UNAVAILABLE,
        )

@router.post("/{user_id}/profile-image", response_model=UserRead)
async def upload_profile_image(
    user_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload or update user profile image
    - Validates ownership/admin rights
    - Handles file upload via CRUD operation
    - Returns updated user data
    """
    if str(current_user.id) != str(user_id) and not current_user.is_admin:
        raise CustomHTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this profile",
            error_code=NOT_AUTHORIZED,
        )

    try:
        return await upload_user_profile_image(db, user_id, file)
    except CustomHTTPException:
        raise
    except Exception as e:
        raise CustomHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Profile image upload failed: {str(e)}",
            error_code=FILE_UPLOAD_ERROR
        )

@router.delete("/{user_id}/profile-image", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile_image(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete user profile image
    - Validates ownership/admin rights
    - Removes file from storage via CRUD operation
    - Clears profile image references
    """
    if str(current_user.id) != str(user_id) and not current_user.is_admin:
        raise CustomHTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this profile",
            error_code=NOT_AUTHORIZED,
        )

    try:
        await delete_user_profile_image(db, user_id)
    except CustomHTTPException:
        raise
    except Exception as e:
        raise CustomHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete profile image: {str(e)}",
            error_code=FILE_UPLOAD_ERROR
        )

@router.get("/{user_id}/profile-image")
async def get_profile_image(
    user_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get signed URL for profile image
    """
    user = await get_user_by_id(db, user_id)
    if not user or not user.profile_image_url:
        raise CustomHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile image not found",
            error_code=FILE_UPLOAD_ERROR,
        )

    try:
        # Extract bucket name and blob path from URL
        parsed_url = urlparse(user.profile_image_url)
        
        # Handle both formats:
        # 1. https://storage.googleapis.com/BUCKET_NAME/path/to/file
        # 2. https://BUCKET_NAME.storage.googleapis.com/path/to/file
        if parsed_url.netloc == 'storage.googleapis.com':
            # Format 1: path is /BUCKET_NAME/path/to/file
            path_parts = parsed_url.path.lstrip('/').split('/')
            if len(path_parts) < 2:
                raise ValueError("Invalid GCS URL structure")
            blob_path = '/'.join(path_parts[1:])
        else:
            # Format 2: netloc is BUCKET_NAME.storage.googleapis.com
            bucket_name = parsed_url.netloc.split('.')[0]
            blob_path = parsed_url.path.lstrip('/')
        
        # Remove any URL query parameters
        blob_path = blob_path.split('?')[0]
        
        logger.info(f"Attempting to access blob at path: {blob_path}")  # Debug logging
        
        blob = bucket.blob(blob_path)
        if not blob.exists():
            logger.error(f"Blob not found at path: {blob_path}")
            raise CustomHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile image not found in storage"
            )

        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=5),
            method="GET"
        )
        
        logger.info(f"Generated signed URL: {signed_url}")  # Debug logging
        return RedirectResponse(url=signed_url)

    except ValueError as e:
        logger.error(f"URL parsing error: {str(e)}")
        raise CustomHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image URL format"
        )
    except GoogleCloudError as e:
        logger.error(f"GCS error: {str(e)}")
        raise CustomHTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service unavailable",
            error_code=GCS_UNAVAILABLE
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise CustomHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate image URL"
        )
