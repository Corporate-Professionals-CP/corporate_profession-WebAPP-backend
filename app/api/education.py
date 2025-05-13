from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from app.db.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.schemas.education import EducationCreate, EducationRead, EducationUpdate
from app.crud.education import (
    create_education,
    get_user_education,
    update_education,
    delete_education
)
from app.core.exceptions import CustomHTTPException

router = APIRouter(prefix="/education", tags=["education"])

@router.post("/", response_model=EducationRead)
async def create(
    data: EducationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        return await create_education(db, current_user, data)
    except CustomHTTPException as e:
        raise e


@router.get("/me", response_model=List[EducationRead])
async def read_my_education(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        return await get_user_education(db, current_user.id)
    except CustomHTTPException as e:
        raise e


@router.put("/{edu_id}", response_model=EducationRead)
async def update(
    edu_id: UUID,
    data: EducationUpdate,
    db: AsyncSession = Depends(get_db)
):
    try:
        return await update_education(db, edu_id, data)
    except CustomHTTPException as e:
        raise e


@router.delete("/{edu_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    edu_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    try:
        deleted = await delete_education(db, edu_id)
        if not deleted:
            raise CustomHTTPException(status_code=404, detail="Education not found")
    except CustomHTTPException as e:
        raise e

