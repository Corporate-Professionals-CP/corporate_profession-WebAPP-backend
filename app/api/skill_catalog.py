from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.database import get_db
from app.schemas.skill import SkillRead
from app.crud import skill as skill_crud

router = APIRouter(prefix="/skills", tags=["skills"])

@router.get("/all", response_model=List[SkillRead])
async def list_all_skills(
    db: AsyncSession = Depends(get_db)
):
    """
    Public endpoint to list all available skills.
    Used by frontend for autocomplete dropdowns.
    """
    return await skill_crud.get_multi(db)

