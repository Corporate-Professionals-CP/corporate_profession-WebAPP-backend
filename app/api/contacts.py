from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.db.database import get_db
from app.core.security import get_current_active_user
from app.models.user import User
from app.schemas.contact import ContactCreate, ContactRead, ContactUpdate
from app.crud.contact import create_contact, get_user_contacts, update_contact, delete_contact
from app.core.exceptions import CustomHTTPException

router = APIRouter(prefix="/contacts", tags=["contacts"])

@router.post("/", response_model=ContactRead)
async def add_contact(
    contact_in: ContactCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        return await create_contact(db, current_user, contact_in)
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Error adding contact: {str(e)}")

@router.get("/", response_model=List[ContactRead])
async def list_contacts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        return await get_user_contacts(db, str(current_user.id))
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Error listing contacts: {str(e)}")

@router.put("/{contact_id}", response_model=ContactRead)
async def edit_contact(
    contact_id: str,
    contact_in: ContactUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        updated = await update_contact(db, contact_id, contact_in)
        if not updated:
            raise CustomHTTPException(status_code=404, detail="Contact not found")
        return updated
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Error updating contact: {str(e)}")

@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_contact(
    contact_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        deleted = await delete_contact(db, contact_id)
        if not deleted:
            raise CustomHTTPException(status_code=404, detail="Contact not found")
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Error deleting contact: {str(e)}")

