from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.db.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.schemas.volunteering import VolunteeringCreate, VolunteeringRead, VolunteeringUpdate
from app.crud.volunteering import (
    create_volunteering,
    get_user_volunteering,
    update_volunteering,
    delete_volunteering
)
from app.core.exceptions import CustomHTTPException

router = APIRouter(prefix="/volunteering", tags=["volunteering"])


@router.post("/", response_model=VolunteeringRead)
async def add_volunteering(
    volunteering_in: VolunteeringCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        return await create_volunteering(db, current_user, volunteering_in)
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[VolunteeringRead])
async def list_volunteering(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        return await get_user_volunteering(db, str(current_user.id))
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=str(e))


@router.put("/{volunteering_id}", response_model=VolunteeringRead)
async def edit_volunteering(
    volunteering_id: str,
    volunteering_in: VolunteeringUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        updated = await update_volunteering(db, volunteering_id, volunteering_in)
        if not updated:
            raise CustomHTTPException(status_code=404, detail="Volunteering experience not found")
        return updated
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=str(e))


@router.delete("/{volunteering_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_volunteering(
    volunteering_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        deleted = await delete_volunteering(db, volunteering_id)
        if not deleted:
            raise CustomHTTPException(status_code=404, detail="Volunteering experience not found")
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=str(e))

