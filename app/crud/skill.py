"""
Complete skill CRUD operations:
- Skill management for multi-select dropdown
- User-skill association handling
"""

from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from sqlalchemy.exc import IntegrityError

from app.models.skill import Skill, UserSkill
from app.core.exceptions import CustomHTTPException


async def get_multi(db: AsyncSession):
    """List all skills for dropdown"""
    result = await db.execute(select(Skill).order_by(Skill.name))
    return result.scalars().all()


async def get_by_ids(db: AsyncSession, skill_ids: List[int]):
    """Get multiple skills by IDs for profile association"""
    result = await db.execute(select(Skill).where(Skill.id.in_(skill_ids)))
    return result.scalars().all()


async def create(db: AsyncSession, name: str):
    """Add new skill with duplicate checking"""
    try:
        skill = Skill(name=name.strip().title())
        db.add(skill)
        await db.commit()
        await db.refresh(skill)
        return skill
    except IntegrityError:
        await db.rollback()
        raise CustomHTTPException(
            status_code=400,
            detail="Skill already exists"
        )
    except Exception:
        await db.rollback()
        raise CustomHTTPException(
            status_code=500,
            detail="An error occurred while creating skill"
        )


async def add_user_skill(db: AsyncSession, user_id: str, skill_id: int):
    """Associate a skill with a user"""
    try:
        association = UserSkill(user_id=user_id, skill_id=skill_id)
        db.add(association)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise CustomHTTPException(
            status_code=400,
            detail="Skill is already associated with this user"
        )
    except Exception:
        await db.rollback()
        raise CustomHTTPException(
            status_code=500,
            detail="Failed to associate skill with user"
        )


async def remove_user_skill(db: AsyncSession, user_id: str, skill_id: int):
    """Remove skill association from user"""
    try:
        result = await db.execute(
            select(UserSkill).where(
                UserSkill.user_id == user_id,
                UserSkill.skill_id == skill_id
            )
        )
        association = result.scalars().first()
        if association:
            await db.delete(association)
            await db.commit()
            return True
        return False
    except Exception:
        await db.rollback()
        raise CustomHTTPException(
            status_code=500,
            detail="Failed to remove skill from user"
        )

