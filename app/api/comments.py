from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.database import get_db
from app.models.post_comment import PostComment
from app.core.security import get_current_user
from app.models.user import User
from app.crud.post_comment import (
    create_comment,
    get_comments_for_post,
    get_comment_by_id,
    update_comment,
    delete_comment,
)
from app.schemas.post_comment import (
    PostCommentCreate as CommentCreate,
    PostCommentUpdate as CommentUpdate,
    PostCommentRead as CommentRead
)
from app.core.exceptions import CustomHTTPException


router = APIRouter(prefix="/comments", tags=["Comments"])

@router.post("/", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
async def add_comment(
    comment_in: CommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        return await create_comment(
            db=db,
            user_id=current_user.id,
            post_id=comment_in.post_id,
            data=comment_in
        )
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Error creating comment: {str(e)}")


@router.get("/post/{post_id}", response_model=List[CommentRead])
async def fetch_comments(
    post_id: str = Path(..., description="ID of the post to fetch comments for"),
    db: AsyncSession = Depends(get_db)
):
    try:
        return await get_comments_for_post(db=db, post_id=post_id)
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Error fetching comments: {str(e)}")


@router.put("/{comment_id}", response_model=CommentRead)
async def edit_comment(
    comment_id: str,
    comment_in: CommentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    comment = await get_comment_by_id(db, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to edit this comment")
    return await update_comment(db=db, comment_id=comment_id, user_id=current_user.id, data=comment_in)


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_comment(
    comment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    comment = await get_comment_by_id(db, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this comment")
    await delete_comment(db=db, comment_id=comment_id, user_id=current_user.id)

