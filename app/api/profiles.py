from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from typing import Union

from app.db.database import get_session
from app.crud.user import get_user_by_id
from app.schemas.user import UserRead, UserPublic, UserUpdate

router = APIRouter()

@router.get("/{user_id}", response_model=Union[UserRead, UserPublic])
def get_profile(user_id: str, session: Session = Depends(get_session)):
    """
    Retrieve a user's profile by their unique ID.
    
    If the user's profile is hidden (hide_profile is True),
    only the user's id and full_name will be returned.
    """
    user = get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.hide_profile:
        # Return minimal public info when the profile is hidden.
        return UserPublic.from_orm(user)
    
    return user

@router.put("/{user_id}", response_model=UserRead)
def update_profile(user_id: str, user_update: UserUpdate, session: Session = Depends(get_session)):
    """
    Update a user's profile.
    
    This endpoint supports updating all profile details including toggles
    for recruiter tag and hide profile.
    """
    updated_user = update_user(session, user_id, user_update)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return updated_user

