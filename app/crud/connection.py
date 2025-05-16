from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, or_
from uuid import UUID
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError

from app.models.connection import Connection
from app.schemas.enums import ConnectionStatus
from app.core.exceptions import CustomHTTPException


async def send_connection_request(db: AsyncSession, sender_id: str, receiver_id: str):
    try:
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
        await db.refresh(conn, attribute_names=["sender", "receiver"])
        return conn
    except SQLAlchemyError:
        await db.rollback()
        raise CustomHTTPException(500, "Failed to send connection request")


async def respond_to_connection(db: AsyncSession, connection_id: str, status: str):
    try:
        result = await db.execute(
            select(Connection)
            .options(joinedload(Connection.sender), joinedload(Connection.receiver))
            .where(Connection.id == connection_id)
        )
        conn = result.scalar_one_or_none()
        if not conn:
            raise CustomHTTPException(404, "Connection request not found")

        conn.status = status
        await db.commit()
        await db.refresh(conn, ["sender", "receiver"])
        return conn
    except CustomHTTPException:
        raise
    except SQLAlchemyError:
        await db.rollback()
        raise CustomHTTPException(500, "Failed to respond to connection request")


async def get_my_requests(db: AsyncSession, user_id: UUID):
    try:
        result = await db.execute(
            select(Connection).where(
                Connection.receiver_id == str(user_id),
                Connection.status == ConnectionStatus.PENDING.value
            )
        )
        return result.scalars().all()
    except SQLAlchemyError:
        raise CustomHTTPException(500, "Failed to retrieve incoming connection requests")


async def get_sent_requests(db: AsyncSession, user_id: UUID):
    try:
        result = await db.execute(
            select(Connection).where(
                Connection.sender_id == str(user_id),
                Connection.status == ConnectionStatus.PENDING.value
            )
        )
        return result.scalars().all()
    except SQLAlchemyError:
        raise CustomHTTPException(500, "Failed to retrieve sent connection requests")


async def get_my_connections(db: AsyncSession, user_id: UUID):
    try:
        result = await db.execute(
            select(Connection)
            .options(joinedload(Connection.sender), joinedload(Connection.receiver))
            .where(
                or_(
                    Connection.sender_id == str(user_id),
                    Connection.receiver_id == str(user_id)
                ),
                Connection.status == ConnectionStatus.ACCEPTED.value
            )
        )
        return result.scalars().all()
    except SQLAlchemyError:
        raise CustomHTTPException(500, "Failed to retrieve your connections")


async def remove_connection(db: AsyncSession, connection_id: str, current_user_id: str) -> bool:
    try:
        result = await db.execute(
            select(Connection).where(
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
            raise CustomHTTPException(404, "Connection not found")

        await db.delete(conn)
        await db.commit()
        return True
    except CustomHTTPException:
        raise
    except SQLAlchemyError:
        await db.rollback()
        raise CustomHTTPException(500, "Failed to remove connection")

