from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from app.models.work_experience import WorkExperience
from app.models.user import User
from app.schemas.work_experience import WorkExperienceCreate, WorkExperienceUpdate
from app.core.exceptions import CustomHTTPException

async def create_work_experience(session: AsyncSession, user: User, data: WorkExperienceCreate) -> WorkExperience:
    try:
        # Convert to dict and handle timezones
        experience_data = data.dict()
        
        # Ensure timezone-naive datetimes
        for date_field in ['start_date', 'end_date']:
            if experience_data.get(date_field) and isinstance(experience_data[date_field], datetime):
                if experience_data[date_field].tzinfo is not None:
                    experience_data[date_field] = experience_data[date_field].replace(tzinfo=None)
        
        experience = WorkExperience(**experience_data, user_id=str(user.id))
        session.add(experience)
        await session.commit()
        await session.refresh(experience)
        return experience
    except Exception as e:
        await session.rollback()
        raise CustomHTTPException(
            status_code=500, 
            detail=f"Error creating work experience: {str(e)}"
        )

async def get_user_work_experiences(session: AsyncSession, user_id: str):
    try:
        result = await session.execute(
            select(WorkExperience)
            .where(WorkExperience.user_id == user_id)
            .order_by(WorkExperience.start_date.desc())
        )
        return result.scalars().all()
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Failed to fetch work experiences: {str(e)}")

async def update_work_experience(
    session: AsyncSession, 
    experience_id: str, 
    data: WorkExperienceUpdate
):
    try:
        experience = await session.get(WorkExperience, experience_id)
        if not experience:
            raise CustomHTTPException(
                status_code=404, 
                detail="Work experience not found"
            )
        
        update_data = data.dict(exclude_unset=True)
        
        # Handle timezone conversion for date fields
        for date_field in ['start_date', 'end_date']:
            if date_field in update_data and update_data[date_field] is not None:
                if isinstance(update_data[date_field], datetime) and update_data[date_field].tzinfo:
                    update_data[date_field] = update_data[date_field].replace(tzinfo=None)
        
        for field, value in update_data.items():
            setattr(experience, field, value)
            
        session.add(experience)
        await session.commit()
        await session.refresh(experience)
        return experience
    except Exception as e:
        await session.rollback()
        raise CustomHTTPException(
            status_code=500, 
            detail=f"Error updating work experience: {str(e)}"
        )

async def delete_work_experience(session: AsyncSession, experience_id: str):
    try:
        experience = await session.get(WorkExperience, experience_id)
        if not experience:
            raise CustomHTTPException(
                status_code=404, 
                detail="Work experience not found"
            )
        await session.delete(experience)
        await session.commit()
        return True
    except Exception as e:
        await session.rollback()
        raise CustomHTTPException(
            status_code=500, 
            detail=f"Error deleting work experience: {str(e)}"
        )
