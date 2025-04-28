"""
Complete user CRUD operations covering all requirements:
- User creation and management
- Profile completion calculation
- Advanced search capabilities
- Bulk operations
- GDPR compliance
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status, UploadFile
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, selectinload
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserPublic, UserDirectoryItem, UserProfileCompletion
from app.utils.file_handling import save_uploaded_file, delete_user_file
from app.models.user import User
from app.models.skill import Skill

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
        .where(User.id == str (user_id)) # convert to string
    )
    return result.scalars().first()

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
    user_update: UserUpdate,
    current_user: User
) -> User:
    """
    Update user profile with security checks
    
    """
    db_user = await get_user_by_id(session, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Authorization check
    if db_user.id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update other users"
        )

    # Validate required fields
    required_fields = ["full_name", "email", "job_title", "industry", "location", "years_of_experience"]
    for field in required_fields:
        if getattr(user_update, field) is None:
            raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{field} is required"
            )

    update_data = user_update.dict(exclude_unset=True)

    # Admin-only fields protection
    if not current_user.is_admin:
        for field in ["is_active", "is_admin", "is_verified",]:
            update_data.pop(field, None)

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

async def search_users(
    session: AsyncSession,
    *,
    query: Optional[str] = None,
    industry: Optional[str] = None,
    experience: Optional[str] = None,
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

async def bulk_update_users(
    session: AsyncSession,
    user_ids: List[UUID],
    update_data: Dict[str, Any]
) -> int:
    """
    Bulk update users (admin only)
   
    """
    result = await session.execute(
        update(User)
        .where(User.id.in_(user_ids))
        .values(update_data)
        .execution_options(synchronize_session="fetch")
    )
    await session.commit()
    return result.rowcount

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
        'cv_url': 5  # Required but gets special handling
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
