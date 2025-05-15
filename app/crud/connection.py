from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, or_
from uuid import UUID
from app.models.connection import Connection
from app.schemas.enums import ConnectionStatus
from sqlalchemy.orm import joinedload


async def send_connection_request(db: AsyncSession, sender_id: str, receiver_id: str):
    result = await db.execute(
        select(Connection)
        .options(joinedload(Connection.sender), joinedload(Connection.receiver))
        .where(
            Connection.sender_id == sender_id,
            Connection.receiver_id == receiver_id,
            Connection.status == ConnectionStatus.PENDING.value
        )
    )

    existing = result.scalar_one_or_none()
    if existing:
        return existing

    conn = Connection(sender_id=sender_id, receiver_id=receiver_id)
    db.add(conn)
    await db.commit()
    await db.refresh(conn)

    # Eagerly load after creation
    await db.refresh(conn, attribute_names=["sender", "receiver"])

    return conn

async def respond_to_connection(db: AsyncSession, connection_id: str, status: str):
    result = await db.execute(
        select(Connection)
        .options(joinedload(Connection.sender), joinedload(Connection.receiver))
        .where(Connection.id == connection_id)
    )
    conn = result.scalar_one_or_none()

    if not conn:
        return None

    conn.status = status
    await db.commit()
    await db.refresh(conn, ["sender", "receiver"])
    return conn 


async def get_my_requests(db: AsyncSession, user_id: UUID):
    user_str = str(user_id)
    result = await db.execute(
        select(Connection).where(
            Connection.receiver_id == user_str,
            Connection.status == ConnectionStatus.PENDING.value
        )
    )
    return result.scalars().all()


async def get_sent_requests(db: AsyncSession, user_id: UUID):
    user_str = str(user_id)
    result = await db.execute(
        select(Connection).where(
            Connection.sender_id == user_str,
            Connection.status == ConnectionStatus.PENDING.value
        )
    )
    return result.scalars().all()

async def get_my_connections(db: AsyncSession, user_id: UUID):
    user_str = str(user_id)
    result = await db.execute(
        select(Connection)
        .options(joinedload(Connection.sender), joinedload(Connection.receiver))
        .where(
            or_(
                Connection.sender_id == user_str,
                Connection.receiver_id == user_str
            ),
            Connection.status == ConnectionStatus.ACCEPTED.value
        )
    )
    return result.scalars().all()


async def remove_connection(
    db: AsyncSession,
    connection_id: str,
    current_user_id: str
) -> bool:
    """
    Removes a connection if the current user is part of it.
    Returns True if deleted, False if not found.
    """
    result = await db.execute(
        select(Connection)
        .where(
            Connection.id == connection_id,
            or_(
                Connection.sender_id == current_user_id,
                Connection.receiver_id == current_user_id
            ),
            Connection.status == ConnectionStatus.ACCEPTED.value
        )
    )
    conn = result.scalar_one_or_none()

    if not conn:
        return False

    await db.delete(conn)
    await db.commit()
    return True
