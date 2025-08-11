from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.models.post_comment import PostComment
from app.models.user import User
from app.models.post import Post
from app.models.notification import Notification
from app.schemas.post_comment import PostCommentCreate, PostCommentUpdate
from app.schemas.enums import NotificationType
from typing import Optional, List
from app.core.exceptions import CustomHTTPException
from fastapi import HTTPException
from sqlalchemy.orm import selectinload
from app.crud.notification import create_notification

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
        
        # Eagerly load the user relationship to avoid lazy loading issues
        result = await db.execute(
            select(PostComment)
            .options(selectinload(PostComment.user))
            .where(PostComment.id == comment.id)
        )
        comment = result.scalar_one()
        
        # Add media_urls to response
        if comment.media_url:
            comment.media_urls = comment.media_url.split(',')
        else:
            comment.media_urls = []
        
        # Create notification for post owner (if not commenting on own post)
        try:
            # Get the post to find the owner
            post_result = await db.execute(select(Post).where(Post.id == post_id))
            post = post_result.scalar_one_or_none()
            
            if post and post.user_id != user_id:
                # Get the commenter's info
                user_result = await db.execute(select(User).where(User.id == user_id))
                commenter = user_result.scalar_one_or_none()
                
                if commenter:
                    await create_notification(
                        db,
                        Notification(
                            recipient_id=post.user_id,
                            actor_id=user_id,
                            type=NotificationType.POST_COMMENT,
                            message=f"{commenter.full_name} commented on your post: '{data.content[:50] + '...' if len(data.content) > 50 else data.content}'",
                            post_id=post_id,
                            comment_id=comment.id
                        )
                    )
        except Exception as notification_error:
            # Log the error but don't fail the comment creation
            print(f"Failed to create notification for comment: {notification_error}")
            
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
            .options(selectinload(PostComment.user))
            .where(PostComment.post_id == post_id)
        )
        return result.scalars().all()
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Failed to fetch comments: {str(e)}")

async def get_comment_by_id(db: AsyncSession, comment_id: str) -> PostComment | None:
    try:
        result = await db.execute(
            select(PostComment)
            .options(selectinload(PostComment.user))
            .where(PostComment.id == comment_id)
        )
        return result.scalar_one_or_none()
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
        comment.updated_at = datetime.utcnow()
        
        if media_urls is not None:  # Explicit None check to allow clearing media
            for url in media_urls or []:
                if not url.startswith("https://storage.googleapis.com/"):
                    raise HTTPException(400, "Invalid media URL format")
            
            comment.media_url = ",".join(media_urls) if media_urls else None
            comment.media_type = _determine_media_type(media_urls) if media_urls else None

        await db.commit()
        await db.refresh(comment)
        
        # Eagerly load the user relationship to avoid lazy loading issues
        result = await db.execute(
            select(PostComment)
            .options(selectinload(PostComment.user))
            .where(PostComment.id == comment.id)
        )
        comment = result.scalar_one()
        
        # Update media_urls for response
        if comment.media_url:
            comment.media_urls = comment.media_url.split(',')
        else:
            comment.media_urls = []
            
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

