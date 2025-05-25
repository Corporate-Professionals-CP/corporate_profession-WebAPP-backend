from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from uuid import UUID

from app.models.bookmark import Bookmark
from app.models.user import User
from app.core.exceptions import CustomHTTPException


async def create_bookmark(db: AsyncSession, user: User, post_id: UUID) -> Bookmark:
    # Check if bookmark already exists
    existing = await db.execute(
        select(Bookmark).where(
            Bookmark.user_id == str(user.id),
            Bookmark.post_id == str(post_id)
        )
    )
    if existing.scalar_one_or_none():
        raise CustomHTTPException(
            status_code=400,
            detail="Post already bookmarked by this user"
        )

    try:
        bookmark = Bookmark(user_id=str(user.id), post_id=str(post_id))
        db.add(bookmark)
        await db.commit()
        await db.refresh(bookmark)
        return bookmark
    except Exception as e:
        await db.rollback()
        raise CustomHTTPException(
            status_code=500,
            detail=f"Failed to create bookmark: {str(e)}"
        )


async def delete_bookmark(db: AsyncSession, user_id: UUID, post_id: UUID) -> bool:
    try:
        result = await db.execute(
            select(Bookmark).where(
                Bookmark.user_id == str(user_id),
                Bookmark.post_id == str(post_id)
            )
        )
        bookmark = result.scalar_one_or_none()
        if not bookmark:
            raise CustomHTTPException(
                status_code=404,
                detail="Bookmark not found"
            )

        await db.delete(bookmark)
        await db.commit()
        return True

    except CustomHTTPException as e:
        raise e

    except Exception:
        await db.rollback()
        raise CustomHTTPException(
            status_code=500,
            detail="Failed to delete bookmark"
        )

