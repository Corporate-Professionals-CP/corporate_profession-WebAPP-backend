from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from typing import List

from app.db.database import get_session
from app.crud.post import create_post, get_post_by_id, update_post, delete_post, list_posts
from app.schemas.post import PostCreate, PostRead, PostUpdate

router = APIRouter()

@router.post("/", response_model=PostRead, status_code=status.HTTP_201_CREATED)
def create_new_post(post: PostCreate, session: Session = Depends(get_session)):
    """
    Create a new post (job opportunity, announcement, or update) for the feed.
    """
    new_post = create_post(session, post)
    return new_post

@router.get("/", response_model=List[PostRead])
def get_posts(offset: int = 0, limit: int = 100, session: Session = Depends(get_session)):
    """
    Retrieve a paginated list of posts.
    
    Optional query parameters:
      - offset: number of posts to skip (for pagination)
      - limit: maximum number of posts to return
    """
    posts = list_posts(session, offset, limit)
    if not posts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No posts found")
    return posts

@router.get("/{post_id}", response_model=PostRead)
def get_post(post_id: str, session: Session = Depends(get_session)):
    """
    Retrieve a single post by its unique ID.
    """
    post = get_post_by_id(session, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post

@router.put("/{post_id}", response_model=PostRead)
def update_existing_post(post_id: str, post_update: PostUpdate, session: Session = Depends(get_session)):
    """
    Update an existing post. Only the fields provided in the request will be updated.
    """
    updated_post = update_post(session, post_id, post_update)
    if not updated_post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return updated_post

@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_post(post_id: str, session: Session = Depends(get_session)):
    """
    Delete a post by its unique ID.
    """
    success = delete_post(session, post_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return None

