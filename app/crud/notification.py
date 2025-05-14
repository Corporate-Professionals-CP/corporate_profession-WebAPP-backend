from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.notification import Notification
from sqlalchemy import select

async def create_notification(db: AsyncSession, notif: Notification) -> Notification:
    db.add(notif)
    await db.commit()
    await db.refresh(notif)
    return notif

async def get_user_notifications(db: AsyncSession, user_id: str):
    result = await db.execute(
        select(Notification)
        .where(Notification.recipient_id == user_id)
        .order_by(Notification.created_at.desc())
    )
    return result.scalars().all()

async def mark_as_read(db: AsyncSession, notif_id: str, user_id: str):
    result = await db.execute(
        select(Notification)
        .where(Notification.id == notif_id, Notification.recipient_id == user_id)
    )
    notif = result.scalar_one_or_none()
    if notif:
        notif.is_read = True
        await db.commit()
        return True
    return False

