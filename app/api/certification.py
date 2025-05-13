from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from app.db.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.schemas.certification import CertificationCreate, CertificationRead, CertificationUpdate
from app.crud.certification import (
    create_certification,
    get_user_certifications,
    update_certification,
    delete_certification
)
from app.core.exceptions import CustomHTTPException

router = APIRouter(prefix="/certification", tags=["certification"])

@router.post("/", response_model=CertificationRead)
async def add_certification(
    data: CertificationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        return await create_certification(db, current_user, data)
    except CustomHTTPException as e:
        raise e

@router.get("/me", response_model=List[CertificationRead])
async def read_my_certifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        return await get_user_certifications(db, current_user.id)
    except CustomHTTPException as e:
        raise e

@router.put("/{cert_id}", response_model=CertificationRead)
async def update(
    cert_id: UUID,
    data: CertificationUpdate,
    db: AsyncSession = Depends(get_db)
):
    try:
        return await update_certification(db, cert_id, data)
    except CustomHTTPException as e:
        raise e

@router.delete("/{cert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    cert_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    try:
        deleted = await delete_certification(db, cert_id)
        if not deleted:
            raise CustomHTTPException(status_code=404, detail="Certification not found")
    except CustomHTTPException as e:
        raise e
