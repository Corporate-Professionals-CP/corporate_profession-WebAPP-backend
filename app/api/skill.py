from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from sqlmodel import select
from sqlalchemy import func

from app.db.database import get_db
from app.models.user import User
from app.core.security import get_current_active_user
from app.crud import skill as skill_crud
from app.schemas.skill import SkillRead, SkillUpdateRequest, SkillCreateRequest
from app.models.skill import Skill
from app.core.exceptions import CustomHTTPException

router = APIRouter(prefix="/skill", tags=["skill"])


@router.get("/", response_model=List[SkillRead])
async def get_my_skills(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        return current_user.skills
    except Exception:
        raise CustomHTTPException(status_code=500, detail="Failed to retrieve skills")


@router.post("/", response_model=List[SkillRead])
async def add_skills_to_profile(
    request: SkillCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        if len(current_user.skills) + len(request.names) > 15:
            raise CustomHTTPException(
                status_code=400, detail="You can only add up to 15 skills"
            )

        added_skills = []
        for name in request.names:
            name_clean = name.strip().title()

            result = await db.execute(
                select(Skill).where(func.lower(Skill.name) == name_clean.lower())
            )
            skill = result.scalars().first()

            if not skill:
                skill = await skill_crud.create(db, name_clean)

            if any(s.id == skill.id for s in current_user.skills):
                raise CustomHTTPException(
                    status_code=400,
                    detail=f"Skill '{name_clean}' is already added to your profile."
                )

            await skill_crud.add_user_skill(db, current_user.id, skill.id)
            added_skills.append(skill)

        return added_skills

    except CustomHTTPException as e:
        raise e
    except Exception:
        raise CustomHTTPException(status_code=500, detail="Failed to add skills to profile")


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_skill_from_profile(
    skill_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        success = await skill_crud.remove_user_skill(db, current_user.id, skill_id)
        if not success:
            raise CustomHTTPException(status_code=404, detail="Skill not found in your profile")
    except CustomHTTPException as e:
        raise e
    except Exception:
        raise CustomHTTPException(status_code=500, detail="Failed to remove skill")


@router.put("/", response_model=List[SkillRead])
async def replace_user_skills(
    request: SkillUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        if len(request.skill_ids) > 15:
            raise CustomHTTPException(status_code=400, detail="Only 15 skills allowed")

        for old_skill in current_user.skills:
            await skill_crud.remove_user_skill(db, current_user.id, old_skill.id)

        new_skills = []
        for sid in request.skill_ids:
            await skill_crud.add_user_skill(db, current_user.id, sid)
            result = await db.execute(select(Skill).where(Skill.id == sid))
            skill = result.scalar_one_or_none()
            if skill:
                new_skills.append(skill)

        return new_skills

    except CustomHTTPException as e:
        raise e
    except Exception:
        raise CustomHTTPException(status_code=500, detail="Failed to update skills")

