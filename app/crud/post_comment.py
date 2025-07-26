from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.models.post_comment import PostComment
from app.models.user import User
from app.schemas.post_comment import PostCommentCreate, PostCommentUpdate
from typing import Optional, List
from app.core.exceptions import CustomHTTPException
from sqlalchemy.orm import selectinload

async def create_comment(
    db: AsyncSession,
    user_id: str,
    post_id: str,
    data: PostCommentCreate,
    media_urls: Optional[List[str]] = None
) -> PostComment:
    try:
        # Validate media URLs if provided
        if media_urls:
            for url in media_urls:
                if not url.startswith("https://storage.googleapis.com/"):
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid media URL format"
                    )

        comment = PostComment(
            user_id=user_id,
            post_id=post_id,
            content=data.content,
            media_url=",".join(media_urls) if media_urls else None,
            media_type=_determine_media_type(media_urls) if media_urls else None
        )
        
        db.add(comment)
        await db.commit()
        await db.refresh(comment)
        
        # Fetch user data separately to avoid relationship issues
        user_result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        
        # Add media_urls to response
        if comment.media_url:
            comment.media_urls = comment.media_url.split(',')
        else:
            comment.media_urls = []
        
        # Manually set user data to avoid relationship access issues
        if user:
            comment._user_data = user
            
        return comment
    except Exception as e:
        raise CustomHTTPException(
            status_code=500,
            detail=f"Failed to create comment: {str(e)}"
        )


async def get_comments_for_post(db: AsyncSession, post_id: str) -> List[PostComment]:
    try:
        result = await db.execute(
            select(PostComment)
            .where(PostComment.post_id == post_id)
        )
        comments = result.scalars().all()
        
        # Fetch user data for each comment
        for comment in comments:
            user_result = await db.execute(
                select(User).where(User.id == comment.user_id)
            )
            user = user_result.scalar_one_or_none()
            if user:
                comment._user_data = user
        
        return comments
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Failed to fetch comments: {str(e)}")

async def get_comment_by_id(db: AsyncSession, comment_id: str) -> PostComment | None:
    try:
        result = await db.execute(
            select(PostComment)
            .where(PostComment.id == comment_id)
        )
        comment = result.scalar_one_or_none()
        
        if comment:
            # Fetch user data separately
            user_result = await db.execute(
                select(User).where(User.id == comment.user_id)
            )
            user = user_result.scalar_one_or_none()
            if user:
                comment._user_data = user
        
        return comment
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Failed to fetch comment by ID: {str(e)}")

async def update_comment(
    db: AsyncSession,
    comment_id: str,
    user_id: str,
    data: PostCommentUpdate,
    media_urls: Optional[List[str]] = None
) -> PostComment:
    try:
        result = await db.execute(
            select(PostComment)
            .where(PostComment.id == comment_id, PostComment.user_id == user_id)
        )
        comment = result.scalar_one_or_none()
        
        if not comment:
            return None

        # Update content and media
        comment.content = data.content
        
        if media_urls is not None:  # Explicit None check to allow clearing media
            for url in media_urls or []:
                if not url.startswith("https://storage.googleapis.com/"):
                    raise HTTPException(400, "Invalid media URL format")
            
            comment.media_url = ",".join(media_urls) if media_urls else None
            comment.media_type = _determine_media_type(media_urls) if media_urls else None

        await db.commit()
        await db.refresh(comment)
        
        # Fetch user data separately to avoid relationship issues
        user_result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        
        # Update media_urls for response
        if comment.media_url:
            comment.media_urls = comment.media_url.split(',')
        else:
            comment.media_urls = []
        
        # Manually set user data to avoid relationship access issues
        if user:
            comment._user_data = user
            
        return comment
    except Exception as e:
        raise CustomHTTPException(
            status_code=500,
            detail=f"Failed to update comment: {str(e)}"
        )

def _determine_media_type(urls: Optional[List[str]]) -> Optional[str]:
    if not urls:
        return None
    if len(urls) > 1:
        return "multiple"
    url = urls[0]
    return "video" if any(ext in url for ext in ["mp4", "mov"]) else "image"

async def delete_comment(db: AsyncSession, comment_id: str, user_id: str) -> bool:
    try:
        result = await db.execute(
            select(PostComment).where(PostComment.id == comment_id, PostComment.user_id == user_id)
        )
        comment = result.scalar_one_or_none()
        if comment:
            await db.delete(comment)
            await db.commit()
            return True
        return False
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Failed to delete comment: {str(e)}")

