"""
profile endpoints implementation
- Profile viewing with privacy controls
- Profile management
- CV upload handling
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Union, Optional
import shutil
import os

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
from app.core.config import settings
from app.utils.file_handling import save_uploaded_file, delete_user_file
from fastapi.responses import FileResponse

router = APIRouter(prefix="/profiles", tags=["profiles"])

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

@router.get("/me", response_model=UserRead)
async def get_own_profile(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current user's full profile (always visible to owner)
    Profile access
    """
    return current_user

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
    return {"completion_percentage": completion}

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

    updated_user = await update_user(db, user_id, user_update)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )

    return updated_user

@router.post("/{user_id}/cv", response_model=UserRead)
async def upload_cv(
    user_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload or update user CV
    - Only owner/admin can upload
    - Supports PDF/DOCX files
    - Stores securely with access control
    """
    # Verify ownership or admin rights
    if str(current_user.id) != str(user_id) and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this profile"
        )

    try:
        # Save file and update user record
        user = await upload_user_cv(db, user_id, file)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User  not found"
            )
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload CV: {str(e)}"
        )

@router.delete("/{user_id}/cv", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cv(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Remove user CV
    Profile management
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
            detail="User  not found"
        )

    if not user.cv_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No CV found to delete"
        )

    try:
        # Remove file and update user record
        await upload_user_cv(db, user_id, None)  # This will delete the CV
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete CV: {str(e)}"
        )

@router.get("/{user_id}/cv", response_class=FileResponse)
async def download_cv(
    user_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Download user CV"""
    user = await get_user_by_id(db, user_id)
    if not user or not user.cv_url:
        raise HTTPException(404, "CV not found")
    
    # Since the CV is stored in Cloudinary, the URL will be returned
    return {"cv_url": user.cv_url}
