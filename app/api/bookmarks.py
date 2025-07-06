import logging
from fastapi import APIRouter, Depends, status, Query, Response
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
from app.crud.post import enrich_multiple_posts
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
        # Main query to get bookmarked posts with user information
        query = (
            select(Post, User)
            .join(Bookmark, Bookmark.post_id == Post.id)
            .join(User, User.id == Post.user_id)
            .where(Bookmark.user_id == str(current_user.id))
            .order_by(Bookmark.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await db.execute(query)
        posts_with_users = result.all()

        if not posts_with_users:
            raise CustomHTTPException(status_code=404, detail="No bookmarks found")

        # Extract posts and users
        posts = [post for post, user in posts_with_users]
        users = [user for post, user in posts_with_users]

        # Use the enrichment function to add all engagement data
        enriched_posts = await enrich_multiple_posts(
            db, posts, users, str(current_user.id)
        )

        return enriched_posts

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
    """Remove a bookmark for a post"""
    try:
        # Verify the post exists first
        post = await db.get(Post, str(post_id))
        if not post:
            raise CustomHTTPException(status_code=404, detail="Post not found")

        # Delete the bookmark regardless of who created the post
        result = await db.execute(
            select(Bookmark).where(
                Bookmark.user_id == str(current_user.id),
                Bookmark.post_id == str(post_id)
            )
        )
        bookmark = result.scalar_one_or_none()
        
        if not bookmark:
            raise CustomHTTPException(status_code=404, detail="Bookmark not found")

        await db.delete(bookmark)
        await db.commit()
        
        # Update bookmark count
        post.engagement["bookmark_count"] = max(0, post.engagement.get("bookmark_count", 1) - 1)
        await db.commit()
        
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except CustomHTTPException as e:
        raise e
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting bookmark: {str(e)}")
        raise CustomHTTPException(
            status_code=500,
            detail="Failed to delete bookmark"
        )



@router.post("/{post_id}/toggle", status_code=200)
async def toggle_bookmark(
    post_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Toggle bookmark status for a post"""
    try:
        # Verify post exists
        post = await db.get(Post, str(post_id))
        if not post:
            raise CustomHTTPException(status_code=404, detail="Post not found")

        # Check existing bookmark
        result = await db.execute(
            select(Bookmark).where(
                Bookmark.user_id == str(current_user.id),
                Bookmark.post_id == str(post_id)
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Delete existing bookmark
            await db.delete(existing)
            post.engagement["bookmark_count"] = max(0, post.engagement.get("bookmark_count", 1) - 1)
            action = False
        else:
            # Create new bookmark
            db.add(Bookmark(user_id=str(current_user.id), post_id=str(post_id)))
            post.engagement["bookmark_count"] = post.engagement.get("bookmark_count", 0) + 1
            action = True

        await db.commit()
        
        # Get enriched post data to return complete information
        post_with_user = await db.execute(
            select(Post, User)
            .join(User, User.id == Post.user_id)
            .where(Post.id == str(post_id))
        )
        post_data = post_with_user.first()
        
        if post_data:
            post, user = post_data
            enriched_posts = await enrich_multiple_posts(
                db, [post], [user], str(current_user.id)
            )
            
            # Return enriched data with bookmark status and counts
            enriched_post = enriched_posts[0]
            return {
                "bookmarked": action, 
                "count": post.engagement["bookmark_count"],
                "post": enriched_post.__dict__
            }
        
        return {"bookmarked": action, "count": post.engagement["bookmark_count"]}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error toggling bookmark: {str(e)}")
        raise CustomHTTPException(
            status_code=500,
            detail="Failed to toggle bookmark"
        )
