from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Optional

from app.db.database import get_session
from app.models.user import User
from app.schemas.directory import DirectorySearchParams, UserDirectoryItem

router = APIRouter()

@router.get("/", response_model=List[UserDirectoryItem])
def search_directory(
    params: DirectorySearchParams = Depends(), 
    session: Session = Depends(get_session)
):
    """
    Search and filter professionals based on various criteria.
    
    You can filter by:
      - name
      - job_title
      - industry
      - location
      - experience
    """
    statement = select(User)
    
    # Apply filters if provided in the query parameters.
    if params.name:
        statement = statement.where(User.full_name.ilike(f"%{params.name}%"))
    if params.job_title:
        statement = statement.where(User.job_title.ilike(f"%{params.job_title}%"))
    if params.industry:
        statement = statement.where(User.industry.ilike(f"%{params.industry}%"))
    if params.location:
        statement = statement.where(User.location.ilike(f"%{params.location}%"))
    if params.experience:
        statement = statement.where(User.years_of_experience == params.experience)
    
    users = session.exec(statement).all()
    
    if not users:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No matching professionals found")
    
    return users

