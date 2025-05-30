from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from uuid import UUID
from app.models.education import Education
from app.models.user import User
from app.schemas.education import EducationCreate, EducationUpdate
from app.core.exceptions import CustomHTTPException

async def create_education(session: AsyncSession, user: User, data: EducationCreate) -> Education:
    try:
        edu = Education(**data.dict(), user_id=str(user.id))
        session.add(edu)
        await session.commit()
        await session.refresh(edu)
        return edu
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Failed to create education entry: {str(e)}")


# Get all education records for a user
async def get_user_education(session: AsyncSession, user_id: UUID):
    try:
        result = await session.execute(
            select(Education).where(Education.user_id == str(user_id))
        )
        education = result.scalars().all()
        return education  # returns [] if none found
    except Exception as e:
        raise CustomHTTPException(
            status_code=500,
            detail=f"Failed to fetch education records: {str(e)}"
        )


async def update_education(session: AsyncSession, edu_id: UUID, data: EducationUpdate) -> Education:
    try:
        result = await session.execute(select(Education).where(Education.id == str(edu_id)))
        edu = result.scalar_one_or_none()
        if not edu:
            raise CustomHTTPException(status_code=404, detail="Education entry not found")

        for field, value in data.dict(exclude_unset=True).items():
            setattr(edu, field, value)
        session.add(edu)
        await session.commit()
        await session.refresh(edu)
        return edu
    except CustomHTTPException:
        raise
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Failed to update education entry: {str(e)}")


async def delete_education(session: AsyncSession, edu_id: UUID) -> bool:
    try:
        result = await session.execute(select(Education).where(Education.id == str(edu_id)))
        edu = result.scalar_one_or_none()
        if edu:
            await session.delete(edu)
            await session.commit()
            return True
        return False
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Failed to delete education entry: {str(e)}")

