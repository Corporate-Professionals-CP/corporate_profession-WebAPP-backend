# app/api/admin.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select
from typing import List, Dict

from app.db.database import get_session
from app.crud.user import list_users, update_user, get_user_by_id
from app.crud.post import list_posts, delete_post
from app.schemas.user import UserRead, UserUpdate
from app.schemas.post import PostRead
from app.core.security import decode_access_token
from app.core.config import settings

router = APIRouter()

# Set up OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_current_admin(token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)):
    """
    Dependency that returns the current user if they are an admin.
    Raises an HTTP 401 or 403 error if authentication fails or if the user is not an admin.
    """
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        ) from e

    user = get_user_by_id(session, user_id)
    if not user or not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough privileges"
        )
    return user

# In-memory store for dropdown options (for job titles and industries).
dropdown_options: Dict[str, List[str]] = {
    "job_titles": ["Software Engineer", "Data Scientist", "Product Manager", "Recruiter"],
    "industries": ["Tech", "Finance", "Healthcare", "Education", "Retail"]
}


@router.get("/users", response_model=List[UserRead])
def admin_list_users(
    offset: int = 0, 
    limit: int = 100, 
    session: Session = Depends(get_session),
    current_admin: dict = Depends(get_current_admin)
):
    """
    Retrieve a paginated list of all users.
    """
    return list_users(session, offset, limit)

@router.put("/users/{user_id}", response_model=UserRead)
def admin_update_user(
    user_id: str, 
    user_update: UserUpdate, 
    session: Session = Depends(get_session),
    current_admin: dict = Depends(get_current_admin)
):
    """
    Update a user's profile. Admin can approve, deactivate, or modify user details.
    """
    updated_user = update_user(session, user_id, user_update)
    if not updated_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return updated_user

@router.get("/users/{user_id}", response_model=UserRead)
def admin_get_user(
    user_id: str, 
    session: Session = Depends(get_session),
    current_admin: dict = Depends(get_current_admin)
):
    """
    Retrieve a single user's profile details.
    """
    user = get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("/dropdowns", response_model=Dict[str, List[str]])
def get_dropdown_options(current_admin: dict = Depends(get_current_admin)):
    """
    Retrieve the current dropdown options for job titles and industries.
    """
    return dropdown_options

@router.put("/dropdowns", response_model=Dict[str, List[str]])
def update_dropdown_options(
    options: Dict[str, List[str]], 
    current_admin: dict = Depends(get_current_admin)
):
    """
    Update dropdown options. Accepts a dictionary with keys like 'job_titles' and 'industries'.
    """
    for key in options:
        if key in dropdown_options:
            dropdown_options[key] = options[key]
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid dropdown key: {key}")
    return dropdown_options


@router.get("/posts", response_model=List[PostRead])
def admin_list_posts(
    offset: int = 0, 
    limit: int = 100, 
    session: Session = Depends(get_session),
    current_admin: dict = Depends(get_current_admin)
):
    """
    Retrieve a list of posts for moderation.
    """
    posts = list_posts(session, offset, limit)
    if not posts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No posts found")
    return posts

@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_post(
    post_id: str, 
    session: Session = Depends(get_session),
    current_admin: dict = Depends(get_current_admin)
):
    """
    Delete a post as part of content moderation.
    """
    success = delete_post(session, post_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return None

