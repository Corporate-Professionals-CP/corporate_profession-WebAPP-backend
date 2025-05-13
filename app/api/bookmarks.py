from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.crud.bookmark import create_bookmark, delete_bookmark
from app.schemas.bookmark import BookmarkCreate, BookmarkRead
from app.core.exceptions import CustomHTTPException

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


@router.post("/", response_model=BookmarkRead, status_code=status.HTTP_201_CREATED)
async def bookmark_post(
    bookmark: BookmarkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        return await create_bookmark(db, current_user, bookmark.post_id)
    except CustomHTTPException as e:
        raise e


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_bookmark(
    post_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        deleted = await delete_bookmark(db, current_user.id, post_id)
        if not deleted:
            raise CustomHTTPException(status_code=404, detail="Bookmark not found")
    except CustomHTTPException as e:
        raise e

