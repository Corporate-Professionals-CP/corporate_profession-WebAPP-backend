"""
Database operations for user management.
Implements CRUD (Create, Read, Update, Delete) operations.
"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserPublic
from app.utils.file_handling import save_uploaded_file, delete_user_file

async def create_user(session: AsyncSession, user_data: UserCreate) -> User:
    """
    Create a new user account with validated data.
    Handles email uniqueness check and password hashing.
    """
    # Check for existing user with same email
    existing_user = await get_user_by_email(session, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create user instance without password fields
    db_user = User(**user_data.dict(exclude={"password", "password_confirmation"}))
    
    # Set hashed password
    db_user.set_password(user_data.password.get_secret_value())
    session.add(db_user)
    
    try:
        await session.commit()
        await session.refresh(db_user)
        return db_user
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Database integrity error"
        )

async def get_user_by_id(session: AsyncSession, user_id: str) -> Optional[User]:
    """
    Retrieve a single user by their UUID.
    Returns None if not found.
    """
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalars().first()

async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    """
    Retrieve a user by email address.
    Used for authentication and duplicate checking.
    """
    result = await session.execute(select(User).where(User.email == email))
    return result.scalars().first()

async def update_user(
    session: AsyncSession,
    user_id: str,
    user_update: UserUpdate,
    current_user: User
) -> User:
    """
    Update user profile with validation:
    - Verifies user exists
    - Checks ownership or admin rights
    - Protects recruiter_tag from non-admin changes
    - Handles database integrity errors
    """
    db_user = await get_user_by_id(session, user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Authorization check
    if str(db_user.id) != str(current_user.id) and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update other users"
        )

    # Prepare update data
    update_data = user_update.dict(exclude_unset=True)
    
    # Protect recruiter_tag from non-admin changes
    if "recruiter_tag" in update_data and not current_user.is_admin:
        del update_data["recruiter_tag"]

    # Apply updates
    for field, value in update_data.items():
        setattr(db_user, field, value)

    try:
        session.add(db_user)
        await session.commit()
        await session.refresh(db_user)
        return db_user
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Database integrity error"
        )

async def search_users(
    session: AsyncSession,
    *,
    query: Optional [str] = None,
    industry: Optional[str] = None,
    experience: Optional[str] = None,
    location: Optional[str] = None,
    full_name: Optional[str] = None,
    job_title: Optional[str] = None,
    company: Optional[str] = None,
    recruiter_only: bool = False,
    hide_hidden: bool = True,
    offset: int = 0,
    limit: int = 100
) -> List[User]:
    """
    Search users with filtering and pagination.
    """
    query = select(User).where(User.is_active == True)
    
    # Apply filters
    if industry:
        query = query.where(User.industry == industry)
    if experience:
        query = query.where(User.years_of_experience == experience)
    if location:
        query = query.where(User.location.ilike(f"%{location}%"))
    if recruiter_only:
        query = query.where(User.recruiter_tag == True)
    if hide_hidden:
        query = query.where(User.hide_profile == False)
    if full_name:
        query = query.where(User.full_name.ilike(f"%{full_name}%"))
    if job_title:
        query = query.where(User.job_title.ilike(f"%{job_title}"))
    if company:
        query = query.where(User.company.ilike(f"%{company}%"))
    # Apply pagination
    query = query.offset(offset).limit(limit)
    
    # Execute query
    result = await session.execute(query)
    return result.scalars().all()

async def get_public_user(
    session: AsyncSession,
    user_id: str
) -> UserPublic:
    """
    Retrieve GDPR-compliant public profile.
    """
    user = await get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return UserPublic.from_user(user)

async def upload_user_cv(
    db: AsyncSession,
    user_id: str,
    file: Optional[UploadFile] = None
) -> Optional[User]:
    """Handle CV upload/removal with cloudinary"""
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    
    try:
        # Delete existing CV if present
        if user.cv_url:
            await delete_user_file(user.cv_url)
            user.cv_url = None
        
        # If file provided, save new CV
        if file:
            user.cv_url = await save_uploaded_file(file, str(user.id))

        await db.commit()
        await db.refresh(user)
        return user
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(400, str(e))