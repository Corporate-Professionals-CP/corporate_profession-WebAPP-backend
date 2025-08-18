"""Moderator management endpoints"""

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from typing import List, Dict, Optional, Any
from pydantic import BaseModel

from app.db.database import get_db
from app.models.user import User
from app.core.security import get_current_active_admin
from app.crud import user as crud_user

router = APIRouter(
    prefix="/admin/moderators",
    tags=["moderator"],
    dependencies=[Depends(get_current_active_admin)]
)

class ModeratorResponse(BaseModel):
    id: str
    email: str
    full_name: str
    is_moderator: bool

@router.get("/", response_model=List[ModeratorResponse])
async def list_moderators(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    """List all moderators"""
    try:
        # Query users with moderator role using ORM
        result = await db.execute(
            select(User).where(User.is_moderator == True)
        )
        moderators = []
        for user in result.scalars().all():
            moderators.append({
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "is_moderator": user.is_moderator
            })
        return moderators
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve moderators: {str(e)}"
        )

@router.post("/{user_id}/make", response_model=ModeratorResponse)
async def make_moderator(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    """Make a user a moderator"""
    try:
        # Get the user
        user = await crud_user.get_user_by_id(db, str(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Set moderator flag
        user.is_moderator = True
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        return {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_moderator": user.is_moderator
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to make user a moderator: {str(e)}"
        )

@router.delete("/{user_id}", response_model=ModeratorResponse)
async def remove_moderator(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_active_admin)
):
    """Remove moderator status from a user"""
    try:
        # Get the user
        user = await crud_user.get_user_by_id(db, str(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Remove moderator flag
        user.is_moderator = False
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        return {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_moderator": user.is_moderator
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove moderator status: {str(e)}"
        )