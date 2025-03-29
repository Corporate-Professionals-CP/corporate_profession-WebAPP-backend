from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Optional

from app.db.database import get_session
from app.models.post import Post
from app.schemas.post import PostRead
from app.crud.user import get_user_by_id
from app.api.auth import oauth2_scheme  # Using token extraction from auth
from app.core.security import decode_access_token

router = APIRouter()

def get_current_user(token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)):
    """
    Retrieves the current authenticated user using the JWT token.
    Raises HTTP 401/404 if invalid or not found.
    """
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials") from e

    user = get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

@router.get("/feed", response_model=List[PostRead])
def get_personalized_feed(
    offset: int = 0,
    limit: int = 20,
    session: Session = Depends(get_session),
    current_user: Optional = Depends(get_current_user)
):
    """
    Returns a personalized feed of posts:
      - If the user is authenticated and has an industry preference, the feed includes posts:
          • That have the same industry as the user's profile
          • General posts (Means industry is None)
      - If the user isn't authenticated or hasn't set an industry,topics, only general posts are returned.
      
    Posts are sorted by creation time (newest first) and support pagination.
    """
    # Build the base query ordered by newest posts first.
    statement = select(Post).order_by(Post.created_at.desc())
    
    if current_user and current_user.industry:
        user_industry = current_user.industry
        # Include posts that are either general or match the user's industry.
        statement = statement.where((Post.industry == None) | (Post.industry == user_industry))
    else:
        # Only general posts if not authenticated or no industry set.
        statement = statement.where(Post.industry == None)
    
    statement = statement.offset(offset).limit(limit)
    posts = session.exec(statement).all()
    
    if not posts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No posts found")
    
    return posts

