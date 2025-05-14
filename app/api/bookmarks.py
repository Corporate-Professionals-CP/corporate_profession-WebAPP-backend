import logging
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List
from sqlalchemy import select, or_, and_, func, desc
from sqlalchemy.sql.expression import literal 
from app.db.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.models.bookmark import Bookmark
from app.models.post import Post, PostEngagement
from app.crud.bookmark import create_bookmark, delete_bookmark
from app.schemas.bookmark import BookmarkCreate, BookmarkRead
from app.schemas.post import PostRead
from app.core.exceptions import CustomHTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])

@router.get("/bookmarks", response_model=List[PostRead])
async def get_user_bookmarks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0)
):
    """Get all posts bookmarked by the current user"""
    try:
        # Main query to get bookmarked posts
        query = (
            select(Post)
            .join(Bookmark, Bookmark.post_id == Post.id)
            .where(Bookmark.user_id == str(current_user.id))
            .order_by(Bookmark.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await db.execute(query)
        posts = result.scalars().all()

        if not posts:
            raise CustomHTTPException(status_code=404, detail="No bookmarks found")

        # Process the results
        response_posts = []
        for post in posts:
            # Get bookmark count for this post
            bookmark_count = await db.scalar(
                select(func.count(Bookmark.id))
                .where(Bookmark.post_id == post.id)
            )

            # Prepare post data
            post_data = {
                **post.__dict__,
                "is_bookmarked": True,  # Since these are bookmarked posts
                "total_comments": getattr(post, "total_comments", 0),
                "total_reactions": getattr(post, "total_reactions", 0),
                "is_active": getattr(post, "is_active", True)  # Ensure is_active is set
            }

            # Ensure engagement data exists
            if not post_data.get("engagement"):
                post_data["engagement"] = {}
            post_data["engagement"]["bookmark_count"] = bookmark_count or 0

            # Convert to PostRead schema
            response_posts.append(PostRead(**post_data))

        return response_posts

    except CustomHTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error fetching bookmarks: {str(e)}")
        raise CustomHTTPException(
            status_code=500,
            detail="An error occurred while fetching bookmarks"
        )


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

@router.post("/{post_id}/bookmark", status_code=200)
async def toggle_bookmark(
    post_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Toggle bookmark status for a post"""
    try:
        post = await db.get(Post, str(post_id))
        if not post:
            raise CustomHTTPException(status_code=404, detail="Post not found")

        existing = await db.execute(
            select(Bookmark).where(
                Bookmark.user_id == str(current_user.id),
                Bookmark.post_id == str(post_id)
            )
        )
        existing = existing.scalar_one_or_none()

        if existing:
            await db.delete(existing)
            post.engagement["bookmark_count"] = max(0, post.engagement.get("bookmark_count", 1) - 1)
            action = False
        else:
            db.add(Bookmark(user_id=str(current_user.id), post_id=str(post_id)))
            post.engagement["bookmark_count"] = post.engagement.get("bookmark_count", 0) + 1
            action = True

        await db.commit()
        return {"bookmarked": action, "count": post.engagement["bookmark_count"]}

    except CustomHTTPException as e:
        raise e
    except Exception:
        raise CustomHTTPException(status_code=500, detail="Something went wrong while opening bookmark")
