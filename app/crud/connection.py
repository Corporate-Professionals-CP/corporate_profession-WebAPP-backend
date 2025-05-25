import logging
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, or_
from uuid import UUID
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func
from app.models.connection import Connection
from app.schemas.enums import ConnectionStatus
from app.core.exceptions import CustomHTTPException
from app.models.user import User

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create console handler
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# Create formatter and add it to the handler
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(ch)

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
        logger.debug(f"Executing query for pending requests to user: {user_id}")
        
        result = await db.execute(
            select(Connection)
            .options(joinedload(Connection.sender), joinedload(Connection.receiver))
            .where(
                Connection.receiver_id == str(user_id),
                Connection.status == ConnectionStatus.PENDING.value
            )
        )
        
        connections = result.scalars().all()
        logger.debug(f"Found {len(connections)} pending requests")
        
        # Debug: Log the first connection's sender if available
        if connections:
            logger.debug(f"First connection sender: {connections[0].sender}")
            logger.debug(f"First connection receiver: {connections[0].receiver}")
        
        return connections
        
    except SQLAlchemyError as e:
        logger.error("Database error in get_my_requests:", exc_info=True)
        raise CustomHTTPException(500, "Failed to retrieve incoming connection requests")

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

async def get_pending_sent_requests(db: AsyncSession, user_id: str):
    """Get all pending connection requests sent by the user"""
    try:
        logger.debug(f"Fetching pending sent requests for user: {user_id}")
        
        query = select(Connection).options(
            joinedload(Connection.receiver)
        ).where(
            Connection.sender_id == user_id,
            Connection.status == ConnectionStatus.PENDING.value
        )
        
        logger.debug(f"Executing query: {query}")
        result = await db.execute(query)
        
        connections = result.scalars().all()
        logger.debug(f"Found {len(connections)} pending sent requests")
        
        if connections:
            logger.debug(f"First connection details - ID: {connections[0].id}, "
                       f"Receiver: {connections[0].receiver_id}, "
                       f"Status: {connections[0].status}")
            
            # Log receiver details if loaded
            if connections[0].receiver:
                logger.debug(f"First connection receiver details - "
                           f"Name: {connections[0].receiver.full_name}, "
                           f"ID: {connections[0].receiver.id}")
            else:
                logger.warning("Receiver not loaded for first connection")
        
        return connections
        
    except SQLAlchemyError as e:
        logger.error("Database error in get_pending_sent_requests: "
                   f"User ID: {user_id}, Error: {str(e)}", exc_info=True)
        raise CustomHTTPException(500, "Failed to retrieve sent pending connection requests")
    except Exception as e:
        logger.error("Unexpected error in get_pending_sent_requests: "
                   f"User ID: {user_id}, Error: {str(e)}", exc_info=True)
        raise CustomHTTPException(500, "Failed to retrieve sent pending connection requests")

async def get_potential_connections(db: AsyncSession, user_id: str, limit: int = 10):
    """Get random users who are not already connected with the current user"""
    try:
        logger.debug(f"Getting potential connections for user {user_id}, limit {limit}")

        # Log the connected users query
        logger.debug("Building connected users subquery...")
        connected_users = select(Connection.receiver_id).where(
            Connection.sender_id == user_id
        ).union(
            select(Connection.sender_id).where(
                Connection.receiver_id == user_id
            )
        ).subquery()
        logger.debug(f"Connected users subquery: {connected_users}")

        # Build and log the main query
        query = (
            select(User)
            .where(
                User.id != user_id,
                ~User.id.in_(connected_users)
            )
            .order_by(func.random())
            .limit(limit)
        )
        logger.debug(f"Executing query: {query}")

        result = await db.execute(query)
        users = result.scalars().all()
        
        logger.debug(f"Found {len(users)} potential connections")
        if users:
            logger.debug(f"First potential connection: ID={users[0].id}, Name={users[0].full_name}")
        
        return users
        
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_potential_connections: {str(e)}", exc_info=True)
        raise CustomHTTPException(500, "Failed to retrieve potential connections")
    except Exception as e:
        logger.error(f"Unexpected error in get_potential_connections: {str(e)}", exc_info=True)
        raise CustomHTTPException(500, "Failed to retrieve potential connections")
