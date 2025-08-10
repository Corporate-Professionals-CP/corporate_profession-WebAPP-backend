"""
Complete user CRUD operations covering all requirements:
- User creation and management
- Profile completion calculation
- Advanced search capabilities
- Bulk operations
- GDPR compliance
"""
import hashlib
import random
import os
from typing import List, Optional, Dict, Any, Union
from uuid import UUID
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select, update, and_, or_
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status, UploadFile
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, selectinload
from app.models.user import User
from app.utils.file_handling import save_uploaded_file, delete_user_file
from app.models.user import User
from app.models.skill import Skill
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserPublic,
    UserDirectoryItem,
    UserProfileCompletion
)
from pydantic import HttpUrl
from app.schemas.enums import (
    ExperienceLevel
)
from app.core.exceptions import CustomHTTPException
from app.core.error_codes import (
    USER_ALREADY_EXISTS,
    USER_NOT_FOUND,
    USER_UPDATE_ERROR,
    USER_DELETE_ERROR,
    USER_SEARCH_ERROR,
    USER_BULK_ACTION_ERROR,
    USER_PROFILE_ERROR,
    FILE_UPLOAD_ERROR,
    FILE_DELETE_ERROR,
    DATABASE_INTEGRITY_ERROR,
    INVALID_USER_DATA,
    CV_UPLOAD_FAILED
)
from app.core.config import settings

async def create_user(session: AsyncSession, user_data: Union[UserCreate, dict]) -> User:
    """
    Create a new user account with full validation
    Supports both UserCreate (email/password) and dict (Google OAuth) inputs
    """
    try:
        # Extract email based on input type
        if isinstance(user_data, dict):
            email = user_data.get("email")
            if not email:
                raise CustomHTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email is required for user creation",
                    error_code=INVALID_USER_DATA
                )
            existing_user = await get_user_by_email(session, email)
        else:
            existing_user = await get_user_by_email(session, user_data.email)

        if existing_user:
            raise CustomHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
                error_code=USER_ALREADY_EXISTS
            )

        # Handle different input types
        if isinstance(user_data, dict):
            # Directly create from dictionary (Google OAuth)
            db_user = User(**user_data)
        else:
            # Handle email/password signup
            user_dict = user_data.dict(exclude={"password", "password_confirmation"})
            db_user = User(**user_dict)
            db_user.set_password(user_data.password.get_secret_value())

        session.add(db_user)
        await session.commit()
        await session.refresh(db_user)
        return db_user

    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database integrity error: {str(e)}"
        )
    except ValueError as e:
        await session.rollback()
        raise CustomHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
            error_code=INVALID_USER_DATA
        )


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> Optional[User]:
    """Retrieve user by UUID with error handling - optimized version"""
    try:
        result = await session.execute(
            select(User).where(User.id == str(user_id))
        )
        return result.scalars().first()
    except Exception as e:
        raise CustomHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user",
            error_code=USER_NOT_FOUND
        )

async def get(session: AsyncSession, user_id: UUID) -> Optional[User]:
    """Get user by ID (alias for get_user_by_id)"""
    return await get_user_by_id(session, user_id)

async def get_user(session: AsyncSession, user_id: UUID) -> Optional[User]:
    """Get user by ID (alias for get_user_by_id)"""
    return await get_user_by_id(session, user_id)

async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    """Case-insensitive email lookup with error handling"""
    try:
        result = await session.execute(
            select(User)
            .options(selectinload(User.skills))
            .where(User.email.ilike(email))
        )
        return result.scalars().first()
    except Exception as e:
        raise CustomHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user by email",
            error_code=USER_NOT_FOUND
        )

async def get_user_by_email_or_username(session: AsyncSession, identifier: str) -> Optional[User]:
    """Retrieve user by email or username"""
    result = await session.execute(
        select(User)
        .options(selectinload(User.skills))
        .where(or_(User.email == identifier, User.username == identifier))
    )
    return result.scalars().first()

async def update_user(
    session: AsyncSession,
    user_id: UUID,
    user_update: Union[UserUpdate, dict],
    current_user: Optional[User] = None
) -> User:
    db_user = await get_user_by_id(session, user_id)
    if not db_user:
        raise CustomHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
            error_code=USER_NOT_FOUND
        )

    # Convert to dict
    if isinstance(user_update, dict):
        update_data = user_update
    else:
        update_data = user_update.dict(exclude_unset=True)

        # Auth check
        if current_user:
            if db_user.id != current_user.id and not current_user.is_admin:
                raise CustomHTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot update other users",
                    error_code=USER_UPDATE_ERROR
                )

            # Only block sensitive fields *if* they are included in the update
            restricted_fields = {"is_active", "is_admin", "is_verified"}
            if not current_user.is_admin:
                unauthorized_fields = restricted_fields & update_data.keys()
                if unauthorized_fields:
                    raise CustomHTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"You are not allowed to update: {', '.join(unauthorized_fields)}",
                        error_code=USER_UPDATE_ERROR
                    )

    # Apply updates
    for field, value in update_data.items():
        if isinstance(value, HttpUrl):
            setattr(db_user, field, str(value))
        else:
            setattr(db_user, field, value)

    try:
        session.add(db_user)
        # Update profile completion after any profile changes
        db_user.update_profile_completion()
        await session.commit()
        await session.refresh(db_user)
        return db_user
    except IntegrityError as e:
        await session.rollback()
        raise CustomHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database error: {str(e)}",
            error_code=DATABASE_INTEGRITY_ERROR
        )



async def get_user_for_update(
    session: AsyncSession, 
    user_id: UUID
) -> Optional[User]:
    result = await session.execute(
        select(User)
        .where(User.id == str(user_id))
        .with_for_update()
    )
    return result.scalars().first()

async def update_user_status(
    session: AsyncSession,
    user_id: UUID,
    is_active: bool,
    current_user: User
) -> User:
    try:
        # Convert UUID to string for database compatibility
        user_str_id = str(user_id)
        
        # Get and lock user record
        result = await session.execute(
            select(User)
            .where(User.id == user_str_id)
            .with_for_update()
        )
        user = result.scalars().first()

        if not user:
            raise CustomHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
                error_code=USER_NOT_FOUND
            )

        if not current_user.is_admin:
            raise CustomHTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required",
                error_code=USER_UPDATE_ERROR
            )

        # Perform update
        user.is_active = is_active
        await session.commit()
        return user

    except SQLAlchemyError as e:
        await session.rollback()
        raise CustomHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
            error_code=DATABASE_INTEGRITY_ERROR
        )
    except CustomHTTPException:
        raise
    except Exception as e:
        raise CustomHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
            error_code=USER_UPDATE_ERROR
        )

async def search_users(
    session: AsyncSession,
    *,
    query: Optional[str] = None,
    industry: Optional[str] = None,
    experience: Optional[ExperienceLevel] = None,
    location: Optional[str] = None,
    skills: Optional[str] = None,
    job_title: Optional[str] = None,
    recruiter_only: bool = False,
    hide_hidden: bool = True,
    offset: int = 0,
    limit: int = 100
) -> List[User]:
    """
    Advanced user search with filters matching PRD requirements
    """
    stmt = select(User).options(selectinload(User.skills))
    
    # Base filter for active users
    stmt = stmt.where(User.is_active == True)

    # Search query filter
    if query:
        stmt = stmt.where(
            or_(
                User.full_name.ilike(f"%{query}%"),
                User.job_title.ilike(f"%{query}%"),
                User.company.ilike(f"%{query}%"),
                User.bio.ilike(f"%{query}%")
            )
        )

    # Industry filter 
    if industry:
        stmt = stmt.where(User.industry == industry)

    # Experience filter
    if experience:
        stmt = stmt.where(User.years_of_experience == experience)

    # Location filter
    if location:
        stmt = stmt.where(User.location.ilike(f"%{location}%"))

    # Job title filter
    if job_title:
        stmt = stmt.where(User.job_title.ilike(f"%{job_title}%"))

    # Skill filter 
    if skills:
        stmt = stmt.join(User.skills).where(Skill.name.ilike(f"%{skills}%"))

    # Recruiter filter 
    if recruiter_only:
        stmt = stmt.where(User.recruiter_tag == True)

    # Privacy filter 
    if hide_hidden:
        stmt = stmt.where(User.hide_profile == False)

    # Pagination
    stmt = stmt.offset(offset).limit(limit)

    result = await session.execute(stmt)
    return result.scalars().all()

async def bulk_user_actions(
    session: AsyncSession,
    user_ids: List[UUID],
    action: str
) -> Dict[str, int]:
    """
    Handle bulk user actions (activate/deactivate/verify)
    Returns counts of processed and successful operations
    Admin Panel and Security & Privacy
    """
    results = {"processed": 0, "success": 0}
    update_data = {}

    # Set update data based on action
    if action == "activate":
        update_data["is_active"] = True
    elif action == "deactivate":
        update_data["is_active"] = False
    elif action == "verify":
        update_data["is_verified"] = True
    else:
        return results  # Invalid action

    for user_id in user_ids:
        try:
            user = await get(session, user_id)
            if user:
                for key, value in update_data.items():
                    setattr(user, key, value)
                session.add(user)
                results["processed"] += 1
                results["success"] += 1
        except Exception:
            results["processed"] += 1
            continue

    await session.commit()
    return results

async def get_filtered_users(
    session: AsyncSession,
    *,
    is_active: Optional[bool] = None,
    is_verified: Optional[bool] = None,
    recruiter_tag: Optional[bool] = None,
    industry: Optional[str] = None,
    experience_level: Optional[ExperienceLevel] = None,
    skip: int = 0,
    limit: int = 100
) -> List[UserDirectoryItem]:
    """
    Get filtered users for admin panel with advanced filtering capabilities
    Matching requirements for admin user management
    """
    stmt = select(User).options(selectinload(User.skills))

    # Apply filters
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    if is_verified is not None:
        stmt = stmt.where(User.is_verified == is_verified)
    if recruiter_tag is not None:
        stmt = stmt.where(User.recruiter_tag == recruiter_tag)
    if industry is not None:
        stmt = stmt.where(User.industry == industry)
    if experience_level is not None:
        stmt = stmt.where(User.years_of_experience == experience_level)

    # Apply pagination
    stmt = stmt.offset(skip).limit(limit)

    result = await session.execute(stmt)
    users = result.scalars().all()
    
    return [UserDirectoryItem.from_orm(user) for user in users]

async def toggle_profile_visibility(
    session: AsyncSession,
    user_id: UUID
) -> User:
    """
    Toggle profile visibility (GDPR compliance)
   
    """
    user = await get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hide_profile = not user.hide_profile
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

async def upload_user_cv(
    session: AsyncSession,
    user_id: UUID,
    file: UploadFile
) -> User:
    """
    Handle CV upload with cloud storage
    
    """
    user = await get_user_by_id(session, user_id)
    if not user:
        raise CustomHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
            error_code=USER_NOT_FOUND
        )

    try:
        # Delete existing CV if present
        if user.cv_url:
            await delete_user_file(user.cv_url)

        # Save new CV
        user.cv_url = await save_uploaded_file(file, f"users/{user_id}/cv")
        user.cv_uploaded_at = datetime.utcnow()

        session.add(user)
        # Update profile completion after CV upload
        user.update_profile_completion()
        await session.commit()
        await session.refresh(user)
        return user
    except CustomHTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        raise CustomHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File upload failed: {str(e)}",
            error_code=FILE_UPLOAD_ERROR
        )

async def delete_user_cv(session: AsyncSession, user_id: UUID) -> User:
    """Remove user's CV"""
    user = await get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.cv_url:
        try:
            success = await delete_user_file(user.cv_url)
            if not success:
                raise CustomHTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to delete CV from storage"
                )
            
            user.cv_url = None
            user.cv_uploaded_at = None
            # Update profile completion after CV deletion
            user.update_profile_completion()
            await session.commit()
            await session.refresh(user)
        except Exception as e:
            await session.rollback()
            raise CustomHTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete CV: {str(e)}"
            )
    return user

def generate_avatar_fallback(user: User) -> tuple[str, str]:
    name = user.full_name or user.username
    initials = "".join([n[0] for n in name.split() if n][:2]).upper()

    # Deterministic color based on user ID
    hash_digest = hashlib.md5(str(user.id).encode()).hexdigest()
    color_palette = [
        "#F44336", "#E91E63", "#9C27B0", "#673AB7",
        "#3F51B5", "#2196F3", "#03A9F4", "#009688",
        "#4CAF50", "#FF9800", "#795548"
    ]
    color = color_palette[int(hash_digest, 16) % len(color_palette)]

    return initials, color

async def upload_user_profile_image(
    session: AsyncSession,
    user_id: UUID,
    file: UploadFile
) -> User:
    """
    Handle profile image upload with cloud storage
    - Deletes old image if exists
    - Uploads new image to configured profile path
    - Updates user record with new URL
    """
    user = await get_user_by_id(session, user_id)
    if not user:
        raise CustomHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
            error_code=USER_NOT_FOUND
        )

    try:
        # Delete existing profile image if present
        if user.profile_image_url:
            await delete_user_file(user.profile_image_url)

        # Save new profile image using the configured base path
        user.profile_image_url = await save_uploaded_file(
            file=file,
            user_id=str(user_id),
            file_type="profile"  # This uses GCS_PROFILE_IMAGE_BASE_PATH from config
        )
        user.profile_image_uploaded_at = datetime.utcnow()

        # Update profile completion after profile image upload
        user.update_profile_completion()
        await session.commit()
        await session.refresh(user)
        return user
        
    except HTTPException as e:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        raise CustomHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Profile image upload failed: {str(e)}",
            error_code=FILE_UPLOAD_ERROR
        )

async def delete_user_profile_image(session: AsyncSession, user_id: UUID) -> None:
    user = await get_user_by_id(session, user_id)
    if not user:
        raise CustomHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
            error_code=USER_NOT_FOUND
        )

    if not user.profile_image_url:
        return  # No image to delete

    try:
        success = await delete_user_file(user.profile_image_url)
        if not success:
            raise CustomHTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete image from storage",
                error_code=FILE_DELETE_ERROR
            )
        # On success, clear the DB field
        user.profile_image_url = None
        user.updated_at = datetime.utcnow()
        # Update profile completion after profile image deletion
        user.update_profile_completion()
        session.add(user)
        await session.commit()
    except CustomHTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        raise CustomHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting profile image: {str(e)}",
            error_code=FILE_DELETE_ERROR
        )


async def get_profile_completion(session: AsyncSession, user_id: UUID) -> UserProfileCompletion:
    """
    Calculate detailed profile completion stats with optimized relationship loading
    """
    try:
        # Use the optimized function that loads relationships only when needed
        user = await get_user_by_id_with_relationships(session, user_id)
        
        if not user:
            raise CustomHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
                error_code=USER_NOT_FOUND
            )

        # Define field weights (total should be 100)
        required_fields = {
            'full_name': 15,
            'email': 10,
            'industry': 10,
            'location': 10,
            'job_title': 10,
            'skills': 15,
            'work_experiences': 15,
            'educations': 15,
        }

        optional_fields = {
            'years_of_experience': 5,
            'bio': 5,
            'certifications': 5,
            'linkedin_profile': 5,
            'cv_url': 5,
            'volunteering_experiences': 5,
            'company': 5,
        }

        completion = {
            'total_score': 0,
            'max_score': 100,
            'sections': {},
            'missing_fields': []
        }

        # Check required fields
        for field, weight in required_fields.items():
            is_completed = False
            
            if field == "skills":
                is_completed = bool(user.skills and len(user.skills) > 0)
            elif field == "work_experiences":
                is_completed = bool(user.work_experiences and len(user.work_experiences) > 0)
            elif field == "educations":
                is_completed = bool(user.educations and len(user.educations) > 0)
            else:
                value = getattr(user, field, None)
                is_completed = bool(value and (not isinstance(value, str) or value.strip() != ""))

            if is_completed:
                completion['total_score'] += weight
                completion['sections'][field] = {"completed": True, "weight": weight, "type": "required"}
            else:
                completion['missing_fields'].append(field)
                completion['sections'][field] = {"completed": False, "weight": weight, "type": "required"}

        # Check optional fields
        for field, weight in optional_fields.items():
            is_completed = False
            
            if field == "certifications":
                is_completed = bool(user.certifications and len(user.certifications) > 0)
            elif field == "volunteering_experiences":
                is_completed = bool(user.volunteering_experiences and len(user.volunteering_experiences) > 0)
            else:
                value = getattr(user, field, None)
                is_completed = bool(value and (not isinstance(value, str) or value.strip() != ""))
                
            if is_completed:
                # Only add if it won't push total_score beyond max_score
                if completion['total_score'] + weight <= completion['max_score']:
                    completion['total_score'] += weight
                    completion['sections'][field] = {"completed": True, "weight": weight, "type": "optional"}
                else:
                    completion['sections'][field] = {"completed": False, "weight": weight, "type": "optional"}
            else:
                completion['sections'][field] = {"completed": False, "weight": weight, "type": "optional"}

        # Compute percentage
        percentage = round((completion['total_score'] / completion['max_score']) * 100, 2)

        # Cap percentage at 100 to satisfy Pydantic validation
        if percentage > 100:
            percentage = 100.0

        return UserProfileCompletion(
            completion_percentage=percentage,
            missing_fields=completion['missing_fields'],
            sections=completion['sections']
        )
        
    except CustomHTTPException:
        raise
    except Exception as e:
        raise CustomHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error calculating profile completion",
            error_code=USER_PROFILE_ERROR
        )



async def get_recently_active_users(
    session: AsyncSession,
    days: int = 7,
    limit: int = 10
) -> List[UserDirectoryItem]:
    """Get users active in last X days"""
    cutoff = datetime.utcnow() - timedelta(days=days)
    stmt = (
        select(User)
        .where(User.last_active_at >= cutoff)
        .order_by(User.last_active_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    users = result.scalars().all()
    return [UserDirectoryItem.from_orm(user) for user in users]

async def count_users_by_industry(session: AsyncSession) -> Dict[str, int]:
    """Statistics for admin dashboard"""
    stmt = select(User.industry, User.is_active)
    result = await session.execute(stmt)
    
    counts = {}
    for industry, is_active in result.all():
        if industry:
            if industry not in counts:
                counts[industry] = {"total": 0, "active": 0}
            counts[industry]["total"] += 1
            if is_active:
                counts[industry]["active"] += 1
    
    return counts

async def get_multi(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 100,
    include_inactive: bool = False
) -> List[User]:
    """Get multiple users with pagination"""
    query = select(User).options(selectinload(User.skills))

    if not include_inactive:
        query = query.where(User.is_active == True)

    result = await session.execute(
        query.order_by(User.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def get_user_by_id_with_relationships(session: AsyncSession, user_id: UUID) -> Optional[User]:
    """Retrieve user with all relationships loaded - use only when needed"""
    try:
        result = await session.execute(
            select(User)
            .options(
                selectinload(User.skills),
                selectinload(User.work_experiences),
                selectinload(User.educations),
                selectinload(User.certifications),
                selectinload(User.volunteering_experiences)
            )
            .where(User.id == str(user_id))
        )
        return result.scalars().first()
    except Exception as e:
        raise CustomHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user with relationships",
            error_code=USER_NOT_FOUND
        )
