from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func, and_
from app.db.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.follow import UserFollow
from app.schemas.follow import FollowingResponse, FollowerResponse
from app.crud.user import get_user_by_id
import anyio

router = APIRouter(prefix="/users", tags=["follow"])

async def validate_and_convert_uuid(user_id: str) -> str:
    """Validate and convert UUID input to string"""
    try:
        uuid_obj = UUID(user_id)
        return str(uuid_obj)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid UUID format"
        )

@router.post("/{user_id}/follow", response_model=dict, status_code=status.HTTP_201_CREATED)
async def follow_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        user_id_str = await validate_and_convert_uuid(user_id)
        user_to_follow = await get_user_by_id(db, user_id_str)
        current_user_id = str(current_user.id)

        if user_to_follow.id == current_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot follow yourself"
            )

        existing = await db.execute(
            select(UserFollow).where(
                UserFollow.follower_id == current_user_id,
                UserFollow.followed_id == user_id_str
            )
        )
        if existing.scalar():
            return {"message": "Already following this user"}

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

@router.get("/me/following", response_model=list[FollowingResponse])
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
        users = result.scalars().all()
        following_list = []

        for user in users:
            user_id = str(user.id)

            # Check if they follow back
            result = await db.execute(
                select(UserFollow).where(
                    UserFollow.follower_id == user_id,
                    UserFollow.followed_id == current_user_id
                )
            )
            follows_back = result.scalar() is not None

            # Get mutual count
            user_a_followers = select(UserFollow.follower_id).where(UserFollow.followed_id == current_user_id)
            user_b_followers = select(UserFollow.follower_id).where(UserFollow.followed_id == user_id)

            mutual_query = select(func.count()).select_from(user_a_followers.intersect(user_b_followers).subquery())
            mutual_result = await db.execute(mutual_query)
            mutual_count = mutual_result.scalar()

            # Get sample mutual usernames
            mutual_ids = user_a_followers.intersect(user_b_followers).subquery()
            sample_result = await db.execute(
                select(User.username)
                .join(mutual_ids, User.id == mutual_ids.c.follower_id)
                .limit(3)
            )
            sample_mutuals = sample_result.scalars().all()

            following_list.append(FollowingResponse(
                id=user.id,
                username=user.username,
                full_name=user.full_name,
                bio=user.bio,
                is_verified=user.is_verified,
                is_following_you=follows_back,
                mutual_followers_count=mutual_count or 0,
                latest_mutual_connections=sample_mutuals
            ))

        return following_list

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve following list: {str(e)}"
        )


@router.get("/me/followers", response_model=list[FollowerResponse])
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
        users = result.scalars().all()
        
        followers_list = []
        sync_session = db.sync_session
        
        for user in users:
            user_id = str(user.id)
            
            # Check if current user follows back
            is_following = await anyio.to_thread.run_sync(
                lambda: sync_session.exec(
                    select(UserFollow).where(
                        UserFollow.follower_id == current_user_id,
                        UserFollow.followed_id == user_id
                    )
                ).first() is not None
            )
            
            # Get mutual followers count
            user_a_followers = select(UserFollow.follower_id).where(UserFollow.followed_id == current_user_id)
            user_b_followers = select(UserFollow.follower_id).where(UserFollow.followed_id == user_id)
            mutual_count = sync_session.exec(
                select(func.count()).select_from(user_a_followers.intersect(user_b_followers).subquery())
            ).scalar()
            
            # Get sample mutuals
            mutual_ids = user_a_followers.intersect(user_b_followers).subquery()
            sample_mutuals = sync_session.exec(
                select(User.username)
                .join(mutual_ids, User.id == mutual_ids.c.follower_id)
                .limit(3)
            ).all()
            
            followers_list.append(FollowerResponse(
                id=user.id,
                username=user.username,
                full_name=user.full_name,
                avatar_url=user.avatar_url,
                bio=user.bio,
                is_verified=user.is_verified,
                is_following=is_following,
                mutual_followers_count=mutual_count or 0,
                latest_mutual_connections=sample_mutuals
            ))
            
        return followers_list

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve followers: {str(e)}"
        )


