"""
Complete user CRUD operations covering all requirements:
- User creation and management
- Profile completion calculation
- Advanced search capabilities
- Bulk operations
- GDPR compliance
"""

from typing import List, Optional, Dict, Any, Union
from uuid import UUID
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession
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

from app.schemas.enums import (
    Location,
    Industry,
    ExperienceLevel,
    JobTitle,
)


async def create_user(session: AsyncSession, user_data: UserCreate) -> User:
    """
    Create a new user account with full validation
    """
    existing_user = await get_user_by_email(session, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Use User model's set_password method directly
    db_user = User(
        **user_data.dict(exclude={"password", "password_confirmation"})
    )
    db_user.set_password(user_data.password.get_secret_value())

    try:
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


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> Optional[User]:
    """Retrieve user by UUID with eager loading of relationships"""
    result = await session.execute(
        select(User)
        .options(selectinload(User.skills))
        .where(User.id == str(user_id))
    )
    return result.scalars().first()


async def get(session: AsyncSession, user_id: UUID) -> Optional[User]:
    """Get user by ID (alias for get_user_by_id)"""
    return await get_user_by_id(session, user_id)

async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    """Case-insensitive email lookup"""
    result = await session.execute(
        select(User)
        .options(selectinload(User.skills))
        .where(User.email.ilike(email))
    )
    return result.scalars().first()

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
    user_update: Union[UserUpdate, dict],  # Accept either type
    current_user: Optional[User] = None
) -> User:
    db_user = await get_user_by_id(session, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Handle both Pydantic model and dictionary input
    if isinstance(user_update, dict):
        update_data = user_update
    else:
        # Authorization checks only for UserUpdate (not for system updates)
        if current_user is not None:
            if db_user.id != current_user.id and not current_user.is_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot update other users"
                )

            # Admin-only fields protection
            if not current_user.is_admin:
                for field in ["is_active", "is_admin", "is_verified"]:
                    if getattr(user_update, field) is not None:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Cannot update {field} without admin privileges"
                        )

        update_data = user_update.dict(exclude_unset=True)

    # Apply updates
    for field, value in update_data.items():
        setattr(db_user, field, value)

    try:
        session.add(db_user)
        await session.commit()
        await session.refresh(db_user)
        return db_user
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database error: {str(e)}"
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
            raise HTTPException(status_code=404, detail="User not found")

        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Admin privileges required")

        # Perform update
        user.is_active = is_active
        await session.commit()
        return user

    except SQLAlchemyError as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )

async def search_users(
    session: AsyncSession,
    *,
    query: Optional[str] = None,
    industry: Optional[Industry] = None,
    experience: Optional[ExperienceLevel] = None,
    location: Optional[Location] = None,
    skills: Optional[str] = None,
    job_title: Optional[JobTitle] = None,
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
    industry: Optional[Industry] = None,
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
        raise HTTPException(status_code=404, detail="User not found")

    try:
        # Delete existing CV if present
        if user.cv_url:
            await delete_user_file(user.cv_url)

        # Save new CV
        user.cv_url = await save_uploaded_file(file, f"users/{user_id}/cv")
        user.cv_uploaded_at = datetime.utcnow()

        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File upload failed: {str(e)}"
        )

async def delete_user_cv(session: AsyncSession, user_id: UUID) -> User:
    """Remove user's CV"""
    user = await get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.cv_url:
        await delete_user_file(user.cv_url)
        user.cv_url = None
        user.cv_uploaded_at = None

        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user

async def get_profile_completion(session: AsyncSession, user_id: UUID) -> UserProfileCompletion:
    """
    Calculate detailed profile completion stats
    """
    user = await get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User  not found")

    required_fields = {
        'full_name': 15,
        'job_title': 15,
        'industry': 10,
        'years_of_experience': 10,
        'location': 10,
        'skills': 10,
        'education': 10,
        'company': 10,
        'bio': 10
    }

    optional_fields = {
        'email': 5,
        'phone': 5,
        'certifications': 5,
        'linkedin_profile': 5,
        'cv_url': 5
    }

    completion = {
        'total_score': 0,
        'max_score': 100,
        'sections': {},
        'missing_fields': []
    }

    # Check required fields
    for field, weight in required_fields.items():
        if getattr(user, field, None):
            completion['total_score'] += weight
            completion['sections'][field] = {
                'completed': True,
                'weight': weight
            }
        else:
            completion['missing_fields'].append(field)
            completion['sections'][field] = {
                'completed': False,
                'weight': weight
            }

    # Check optional fields
    for field, weight in optional_fields.items():
        if getattr(user, field, None):
            completion['total_score'] += weight
            completion['sections'][field] = {
                'completed': True,
                'weight': weight
            }

    # Special CV handling (required but in optional fields)
    if not user.cv_url:
        completion['missing_fields'].append('cv_url')

    # Calculate completion percentage
    completion_percentage = (completion['total_score'] / completion['max_score']) * 100
    print(f"Completion Percentage: {completion_percentage}") # debugging

    # Return the UserProfileCompletion instance
    return UserProfileCompletion(
        completion_percentage=completion_percentage,
        missing_fields=completion['missing_fields'],
        sections=completion['sections']
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
