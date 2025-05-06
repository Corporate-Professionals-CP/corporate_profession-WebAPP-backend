from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.db.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.follow import UserFollow

router = APIRouter(prefix="/users", tags=["follow"])

async def validate_and_convert_uuid(user_id: str) -> str:
    """Validate and convert UUID input to string"""
    try:
        # Validate UUID format
        uuid_obj = UUID(user_id)
        return str(uuid_obj)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid UUID format"
        )

async def get_user_by_id(db: AsyncSession, user_id: str) -> User:
    """Get user with proper error handling"""
    try:
        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

@router.post("/{user_id}/follow", response_model=dict, status_code=status.HTTP_201_CREATED)
async def follow_user(
    user_id: str,  # Accept as string
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # Validate and convert UUID
        user_id_str = await validate_and_convert_uuid(user_id)
        
        # Get users
        user_to_follow = await get_user_by_id(db, user_id_str)
        current_user_id = str(current_user.id)  # Ensure string conversion
        
        # Check self-follow
        if user_to_follow.id == current_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot follow yourself"
            )
        
        # Check existing relationship
        existing = await db.execute(
            select(UserFollow).where(
                UserFollow.follower_id == current_user_id,
                UserFollow.followed_id == user_id_str
            )
        )
        if existing.scalar():
            return {"message": "Already following this user"}
        
        # Create new relationship
        follow_entry = UserFollow(
            follower_id=current_user_id,
            followed_id=user_id_str
        )
        db.add(follow_entry)
        await db.commit()
        await db.refresh(follow_entry)
        
        return {"message": f"Successfully followed user {user_id_str}"}

    except HTTPException as he:
        raise he
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Operation failed: {str(e)}"
        )

@router.delete("/{user_id}/unfollow", response_model=dict)
async def unfollow_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        user_id_str = await validate_and_convert_uuid(user_id)
        current_user_id = str(current_user.id)
        
        # Find relationship
        result = await db.execute(
            select(UserFollow).where(
                UserFollow.follower_id == current_user_id,
                UserFollow.followed_id == user_id_str
            )
        )
        follow_entry = result.scalar_one_or_none()
        
        if not follow_entry:
            return {"message": "No existing follow relationship"}
        
        await db.delete(follow_entry)
        await db.commit()
        return {"message": f"Successfully unfollowed user {user_id_str}"}

    except HTTPException as he:
        raise he
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unfollow operation failed: {str(e)}"
        )

@router.get("/me/following", response_model=list[User])
async def get_following(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        current_user_id = str(current_user.id)
        result = await db.execute(
            select(User)
            .join(UserFollow, User.id == UserFollow.followed_id)
            .where(UserFollow.follower_id == current_user_id)
        )
        return result.scalars().all()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve following list: {str(e)}"
        )

@router.get("/me/followers", response_model=list[User])
async def get_followers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        current_user_id = str(current_user.id)
        result = await db.execute(
            select(User)
            .join(UserFollow, User.id == UserFollow.follower_id)
            .where(UserFollow.followed_id == current_user_id)
        )
        return result.scalars().all()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve followers: {str(e)}"
        )
