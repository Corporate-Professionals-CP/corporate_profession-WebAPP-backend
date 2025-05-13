from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.volunteering import Volunteering
from app.models.user import User
from app.schemas.volunteering import VolunteeringCreate, VolunteeringUpdate
from app.core.exceptions import CustomHTTPException


async def create_volunteering(session: AsyncSession, user: User, data: VolunteeringCreate) -> Volunteering:
    try:
        volunteering = Volunteering(**data.dict(), user_id=str(user.id))
        session.add(volunteering)
        await session.commit()
        await session.refresh(volunteering)
        return volunteering
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Error creating volunteering experience: {str(e)}")


async def get_user_volunteering(session: AsyncSession, user_id: str):
    try:
        result = await session.execute(select(Volunteering).where(Volunteering.user_id == user_id))
        return result.scalars().all()
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Error retrieving volunteering experiences: {str(e)}")


async def update_volunteering(session: AsyncSession, volunteering_id: str, data: VolunteeringUpdate):
    try:
        volunteering = await session.get(Volunteering, volunteering_id)
        if not volunteering:
            return None
        for field, value in data.dict(exclude_unset=True).items():
            setattr(volunteering, field, value)
        session.add(volunteering)
        await session.commit()
        await session.refresh(volunteering)
        return volunteering
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Error updating volunteering experience: {str(e)}")


async def delete_volunteering(session: AsyncSession, volunteering_id: str):
    try:
        volunteering = await session.get(Volunteering, volunteering_id)
        if volunteering:
            await session.delete(volunteering)
            await session.commit()
            return True
        return False
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Error deleting volunteering experience: {str(e)}")

