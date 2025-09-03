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
from datetime import timedelta, datetime
from app.db.database import get_db
from app.models.user import User
from app.schemas.user import UserRead, UserPublic, UserUpdate, UserProfileCompletion, UserProfileResponse, DownloadCVResponse, ProfileImageResponse
from app.core.security import get_current_active_user, get_current_active_admin
from app.crud.user import (
    get_user_by_id,
    get_user_by_id_with_relationships,
    update_user,
    upload_user_cv,
    delete_user_cv,
    get_profile_completion,
    upload_user_profile_image,
    delete_user_profile_image,
    generate_avatar_fallback
)
from app.crud.work_experience import get_user_work_experiences
from app.crud.education import get_user_education
from app.crud.contact import get_user_contacts
from google.cloud.exceptions import GoogleCloudError
from urllib.parse import urlparse
from app.core.config import settings
from app.schemas.user import UserUpdate as UserUpdateSchema
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
    ADMIN_PRIVILEGE_REQUIRED,
    FILE_UPLOAD_ERROR
)
logger = logging.getLogger(__name__)


router = APIRouter(prefix="/profiles", tags=["profiles"])

@router.get("/me", response_model=UserRead)
async def get_own_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current user's full profile (always visible to owner)
    """
    profile_completion = await get_profile_completion(db, current_user.id)

    # Refresh user data from database to ensure we have the latest profile image info
    fresh_user = await get_user_by_id(db, current_user.id)
    if not fresh_user:
        fresh_user = current_user
    
    user_data = UserRead.from_orm(fresh_user)
    user_data.profile_completion = profile_completion.completion_percentage
    user_data.missing_fields = profile_completion.missing_fields
    user_data.sections = profile_completion.sections
    
    # Add cache-busting parameter to profile image URL
    if user_data.profile_image_url and fresh_user.profile_image_uploaded_at:
        user_data.profile_image_url = f"{user_data.profile_image_url}?v={int(fresh_user.profile_image_uploaded_at.timestamp())}"

    return user_data

@router.get("/{user_id}", response_model=Union[UserProfileResponse, UserPublic])
async def get_profile(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    is_owner_or_admin = str(current_user.id) == str(user_id) or current_user.is_admin

    user = await get_user_by_id_with_relationships(db, user_id)
    if not user:
        raise CustomHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
            error_code=USER_NOT_FOUND,
        )

    if is_owner_or_admin or not user.hide_profile:
        work_experience = await get_user_work_experiences(db, str(user.id)) or []
        education = await get_user_education(db, str(user.id)) or []
        contact = await get_user_contacts(db, str(user.id)) or []

        initials, color = generate_avatar_fallback(user)

        return UserProfileResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            bio=user.bio,
            job_title=user.job_title,
            recruiter_tag=user.recruiter_tag,
            is_active=user.is_active,
            is_admin=user.is_admin,
            created_at=user.created_at,
            updated_at=user.updated_at,
            work_experience=work_experience,
            education=education,
            years_of_experience=user.years_of_experience,
            industry=user.industry,
            status=user.status,
            visibility=user.visibility,
            contact=contact,
            location=user.location,
            profile_image_url=f"{user.profile_image_url}?v={int(user.profile_image_uploaded_at.timestamp())}" if user.profile_image_url and user.profile_image_uploaded_at else user.profile_image_url,
            skills=user.skills or [],
            avatar_text=initials,
            avatar_color=color
        )

    return UserPublic(
        id=user.id,
        full_name=user.full_name,
        status=user.status,
        recruiter_tag=user.recruiter_tag,
        visibility=user.visibility,
        industry=user.industry,
        location=user.location,
        years_of_experience=user.years_of_experience

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
        required_fields = ["full_name", "job_title", "industry", "location", "years_of_experience"]
        for field in required_fields:
            if getattr(user_update, field) is None and getattr(user, field) is None:
                raise CustomHTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{field} is required for professional users",
                    error_code=REQUIRED_FIELD_MISSING,
                )


    # Exclude profile image fields from general updates to prevent accidental overwrites
    update_data = user_update.dict(exclude_unset=True)
    if 'profile_image_url' in update_data:
        del update_data['profile_image_url']
    if 'profile_image_uploaded_at' in update_data:
        del update_data['profile_image_uploaded_at']
    
    # Create a new UserUpdate object without profile image fields
    filtered_update = UserUpdateSchema(**update_data)
    
    updated_user = await update_user(db, user_id, filtered_update, current_user)

    # Get updated profile completion
    profile_completion = await get_profile_completion(db, user_id)

    # Convert to UserRead and add profile completion data
    user_data = UserRead.from_orm(updated_user)
    user_data.profile_completion = profile_completion.completion_percentage
    user_data.missing_fields = profile_completion.missing_fields
    user_data.sections = profile_completion.sections
    
    # Add cache-busting parameter to profile image URL
    if user_data.profile_image_url and updated_user.profile_image_uploaded_at:
        user_data.profile_image_url = f"{user_data.profile_image_url}?v={int(updated_user.profile_image_uploaded_at.timestamp())}"

    return user_data


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

@router.get("/{user_id}/cv", response_model=DownloadCVResponse)
async def get_cv_download_url(
    user_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a signed URL for downloading a user's CV
    Returns:
        {
            "download_url": "https://signed-gcs-url.com/path/to/cv.pdf",
            "expires_at": "2023-01-01T00:05:00Z"  # When the URL expires
        }
    """
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
            raise CustomHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="CV file not found in storage",
                error_code=CV_NOT_FOUND
            )

        # Generate fresh signed URL with 5 minute expiration
        expiration = timedelta(minutes=5)
        download_url = blob.generate_signed_url(
            version="v4",
            expiration=expiration,
            method="GET"
        )

        return {
            "download_url": download_url,
            "expires_at": (datetime.utcnow() + expiration).isoformat()
        }

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
        updated_user = await upload_user_profile_image(db, user_id, file)
        
        # Ensure the response includes cache-busted profile image URL
        user_data = UserRead.from_orm(updated_user)
        if user_data.profile_image_url and updated_user.profile_image_uploaded_at:
            user_data.profile_image_url = f"{user_data.profile_image_url}?v={int(updated_user.profile_image_uploaded_at.timestamp())}"
        
        return user_data
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

@router.get("/{user_id}/profile-image", response_model=ProfileImageResponse)
async def get_profile_image_url(
    user_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get signed URL for profile image
    Returns:
        {
            "image_url": "https://signed-gcs-url.com/path/to/image.jpg",
            "expires_at": "2023-01-01T00:05:00Z"  # When the URL expires
        }
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

        # Handle both URL formats
        if parsed_url.netloc == 'storage.googleapis.com':
            path_parts = parsed_url.path.lstrip('/').split('/')
            if len(path_parts) < 2:
                raise ValueError("Invalid GCS URL structure")
            blob_path = '/'.join(path_parts[1:])
        else:
            bucket_name = parsed_url.netloc.split('.')[0]
            blob_path = parsed_url.path.lstrip('/')

        # Remove query parameters
        blob_path = blob_path.split('?')[0]

        logger.info(f"Attempting to access blob at path: {blob_path}")

        blob = bucket.blob(blob_path)
        if not blob.exists():
            logger.error(f"Blob not found at path: {blob_path}")
            raise CustomHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile image not found in storage"
            )

        # Generate signed URL with 5 minute expiration
        expiration = timedelta(minutes=5)
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=expiration,
            method="GET"
        )

        logger.info(f"Generated signed URL: {signed_url}")
        return {
            "image_url": signed_url,
            "expires_at": (datetime.utcnow() + expiration).isoformat()
        }

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
