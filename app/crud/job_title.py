from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.models.job_title import JobTitle
from app.core.exceptions import CustomHTTPException
from sqlalchemy.exc import IntegrityError

async def get_all(db: AsyncSession):
    result = await db.execute(select(JobTitle).order_by(JobTitle.name))
    return result.scalars().all()

async def create(db: AsyncSession, name: str):
    try:
        name = name.strip().title()
        job_title = JobTitle(name=name)
        db.add(job_title)
        await db.commit()
        await db.refresh(job_title)
        return job_title
    except IntegrityError:
        await db.rollback()
        raise CustomHTTPException(status_code=400, detail="Job title already exists")

