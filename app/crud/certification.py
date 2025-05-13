from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from uuid import UUID
from app.models.certification import Certification
from app.models.user import User
from app.schemas.certification import CertificationCreate, CertificationUpdate
from app.core.exceptions import CustomHTTPException

async def create_certification(session: AsyncSession, user: User, data: CertificationCreate) -> Certification:
    try:
        cert = Certification(**data.dict(), user_id=str(user.id))
        session.add(cert)
        await session.commit()
        await session.refresh(cert)
        return cert
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Failed to create certification: {str(e)}")

async def get_user_certifications(session: AsyncSession, user_id: UUID):
    try:
        result = await session.execute(select(Certification).where(Certification.user_id == str(user_id)))
        return result.scalars().all()
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Failed to fetch certifications: {str(e)}")

async def update_certification(session: AsyncSession, cert_id: UUID, data: CertificationUpdate) -> Certification:
    try:
        result = await session.execute(select(Certification).where(Certification.id == str(cert_id)))
        cert = result.scalar_one_or_none()
        if not cert:
            raise CustomHTTPException(status_code=404, detail="Certification not found")

        for field, value in data.dict(exclude_unset=True).items():
            setattr(cert, field, value)
        session.add(cert)
        await session.commit()
        await session.refresh(cert)
        return cert
    except CustomHTTPException:
        raise
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Failed to update certification: {str(e)}")

async def delete_certification(session: AsyncSession, cert_id: UUID) -> bool:
    try:
        result = await session.execute(select(Certification).where(Certification.id == str(cert_id)))
        cert = result.scalar_one_or_none()
        if cert:
            await session.delete(cert)
            await session.commit()
            return True
        return False
    except Exception as e:
        raise CustomHTTPException(status_code=500, detail=f"Failed to delete certification: {str(e)}")
