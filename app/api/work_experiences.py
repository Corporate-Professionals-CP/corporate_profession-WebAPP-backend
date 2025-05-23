from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.db.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.schemas.work_experience import (
    WorkExperienceCreate,
    WorkExperienceRead,
    WorkExperienceUpdate,
    WorkExperienceListResponse
)
from app.crud.work_experience import (
    create_work_experience,
    get_user_work_experiences,
    update_work_experience,
    delete_work_experience
)
from app.core.exceptions import CustomHTTPException

router = APIRouter(prefix="/work-experiences", tags=["work_experiences"])

@router.post("/", response_model=WorkExperienceRead)
async def add_work_experience(
    experience_in: WorkExperienceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        return await create_work_experience(db, current_user, experience_in)
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Error adding work experience: {str(e)}")

@router.get("/", response_model=WorkExperienceListResponse)
async def list_work_experiences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        experiences = await get_user_work_experiences(db, str(current_user.id))
        return {"data": experiences}
    except Exception as e:
        raise CustomHTTPException(
            status_code=500,
            detail=f"Error retrieving work experiences: {str(e)}"
        )

@router.put("/{experience_id}", response_model=WorkExperienceRead)
async def edit_work_experience(
    experience_id: str,
    experience_in: WorkExperienceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        updated = await update_work_experience(db, experience_id, experience_in)
        if not updated:
            raise CustomHTTPException(status_code=404, detail="Work experience not found")
        return updated
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Error updating work experience: {str(e)}")

@router.delete("/{experience_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_work_experience(
    experience_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        deleted = await delete_work_experience(db, experience_id)
        if not deleted:
            raise CustomHTTPException(status_code=404, detail="Work experience not found")
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Error deleting work experience: {str(e)}")

