import logging
from typing import List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, or_, and_
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
        # Check for any existing connection between these users (in any direction)
        result = await db.execute(
            select(Connection)
            .options(joinedload(Connection.sender), joinedload(Connection.receiver))
            .where(
                or_(
                    # Check if sender already sent request to receiver
                    and_(
                        Connection.sender_id == sender_id,
                        Connection.receiver_id == receiver_id
                    ),
                    # Check if receiver already sent request to sender
                    and_(
                        Connection.sender_id == receiver_id,
                        Connection.receiver_id == sender_id
                    )
                )
            )
        )

        existing = result.scalar_one_or_none()
        if existing:
            # If connection exists in any status, handle appropriately
            if existing.status == ConnectionStatus.PENDING.value:
                if existing.sender_id == sender_id:
                    # User already sent a request
                    raise CustomHTTPException(400, "Connection request already sent")
                else:
                    # The other user sent a request, user should accept/reject instead
                    raise CustomHTTPException(400, "You have a pending connection request from this user. Please respond to it instead.")
            elif existing.status == ConnectionStatus.ACCEPTED.value:
                raise CustomHTTPException(400, "You are already connected with this user")
            elif existing.status == ConnectionStatus.REJECTED.value:
                # Allow sending new request if previous was rejected
                if existing.sender_id == sender_id:
                    # Update existing rejected request to pending
                    existing.status = ConnectionStatus.PENDING.value
                    existing.created_at = datetime.utcnow()
                    await db.commit()
                    await db.refresh(existing, attribute_names=["sender", "receiver"])
                    return existing
                else:
                    # Create new request in opposite direction
                    pass

        # Create new connection request
        conn = Connection(sender_id=sender_id, receiver_id=receiver_id)
        db.add(conn)
        await db.commit()
        await db.refresh(conn)
        await db.refresh(conn, attribute_names=["sender", "receiver"])
        return conn
    except CustomHTTPException:
        raise
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

async def get_connection_status(db: AsyncSession, user_id: str, other_user_id: str) -> dict:
    """Get connection status between two users"""
    try:
        result = await db.execute(
            select(Connection).where(
                or_(
                    (
                        (Connection.sender_id == user_id) &
                        (Connection.receiver_id == other_user_id)
                    ),
                    (
                        (Connection.sender_id == other_user_id) &
                        (Connection.receiver_id == user_id)
                    )
                )
            ).order_by(Connection.created_at.desc())
        )
        
        connection = result.scalars().first()
        
        if not connection:
            return {
                "status": "none",
                "action": "connect",
                "can_send_request": True
            }
        
        if connection.status == ConnectionStatus.ACCEPTED.value:
            return {
                "status": "connected",
                "action": "remove",
                "can_send_request": False
            }
        elif connection.status == ConnectionStatus.PENDING.value:
            if connection.sender_id == user_id:
                # Current user sent the request
                return {
                    "status": "pending_sent",
                    "action": "cancel",
                    "can_send_request": False
                }
            else:
                # Other user sent the request
                return {
                    "status": "pending_received",
                    "action": "respond",
                    "can_send_request": False,
                    "connection_id": str(connection.id)
                }
        elif connection.status == ConnectionStatus.REJECTED.value:
            return {
                "status": "rejected",
                "action": "connect",
                "can_send_request": True
            }
        
        return {
            "status": "unknown",
            "action": "connect",
            "can_send_request": True
        }
        
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_connection_status: {str(e)}", exc_info=True)
        raise CustomHTTPException(500, "Failed to get connection status")

async def get_potential_connections(db: AsyncSession, user_id: str, limit: int = 10):
    """Get suggested connections prioritizing new users from same industry, excluding connected users"""
    try:
        logger.debug(f"Getting potential connections for user {user_id}, limit {limit}")

        # First, get the current user's industry
        current_user_result = await db.execute(
            select(User.industry).where(User.id == user_id)
        )
        current_user_industry = current_user_result.scalar_one_or_none()
        logger.debug(f"Current user industry: {current_user_industry}")

        # Get all existing connections and pending requests to exclude them
        existing_connections_query = select(Connection.sender_id, Connection.receiver_id).where(
            or_(
                Connection.sender_id == user_id,
                Connection.receiver_id == user_id
            ),
            Connection.status.in_([ConnectionStatus.ACCEPTED.value, ConnectionStatus.PENDING.value])
        )
        
        existing_connections_result = await db.execute(existing_connections_query)
        existing_connections = existing_connections_result.all()
        
        # Create a set of user IDs to exclude (connected or pending)
        excluded_user_ids = set()
        for conn in existing_connections:
            if conn.sender_id == user_id:
                excluded_user_ids.add(conn.receiver_id)
            else:
                excluded_user_ids.add(conn.sender_id)
        
        logger.debug(f"Excluding {len(excluded_user_ids)} users (connected/pending)")

        # Build the main query to get potential connections
        base_conditions = [
            User.id != user_id,  # Exclude current user
            User.is_active == True,  # Only active users
            User.hide_profile == False,  # Only visible profiles
        ]
        
        # Exclude already connected/pending users
        if excluded_user_ids:
            base_conditions.append(~User.id.in_(excluded_user_ids))

        potential_connections = []
        
        # Priority 1: New users from same industry (joined in last 30 days)
        if current_user_industry and len(potential_connections) < limit:
            logger.debug("Fetching new users from same industry")
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            
            same_industry_new_query = (
                select(User)
                .where(
                    and_(
                        *base_conditions,
                        User.industry == current_user_industry,
                        User.created_at >= thirty_days_ago
                    )
                )
                .order_by(User.created_at.desc())  # Newest first
                .limit(limit)
            )
            
            result = await db.execute(same_industry_new_query)
            same_industry_new_users = result.scalars().all()
            
            for user in same_industry_new_users:
                if len(potential_connections) >= limit:
                    break
                    
                user_dict = await _format_user_for_suggestions(user)
                potential_connections.append(user_dict)
            
            logger.debug(f"Found {len(same_industry_new_users)} new users from same industry")

        # Priority 2: Other users from same industry (if we need more)
        if current_user_industry and len(potential_connections) < limit:
            logger.debug("Fetching other users from same industry")
            remaining_limit = limit - len(potential_connections)
            
            # Exclude users already added
            already_added_ids = {user["id"] for user in potential_connections}
            
            same_industry_query = (
                select(User)
                .where(
                    and_(
                        *base_conditions,
                        User.industry == current_user_industry,
                        ~User.id.in_(already_added_ids) if already_added_ids else True
                    )
                )
                .order_by(func.random())
                .limit(remaining_limit * 2)  # Get more to have options
            )
            
            result = await db.execute(same_industry_query)
            same_industry_users = result.scalars().all()
            
            for user in same_industry_users:
                if len(potential_connections) >= limit:
                    break
                    
                user_dict = await _format_user_for_suggestions(user)
                potential_connections.append(user_dict)
            
            logger.debug(f"Added {len(same_industry_users)} more users from same industry")

        # Priority 3: New users from any industry (if we still need more)
        if len(potential_connections) < limit:
            logger.debug("Fetching new users from any industry")
            remaining_limit = limit - len(potential_connections)
            
            # Exclude users already added
            already_added_ids = {user["id"] for user in potential_connections}
            
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            
            new_users_query = (
                select(User)
                .where(
                    and_(
                        *base_conditions,
                        User.created_at >= thirty_days_ago,
                        ~User.id.in_(already_added_ids) if already_added_ids else True
                    )
                )
                .order_by(User.created_at.desc())
                .limit(remaining_limit * 2)
            )
            
            result = await db.execute(new_users_query)
            new_users = result.scalars().all()
            
            for user in new_users:
                if len(potential_connections) >= limit:
                    break
                    
                user_dict = await _format_user_for_suggestions(user)
                potential_connections.append(user_dict)
            
            logger.debug(f"Added {len(new_users)} new users from any industry")

        # Priority 4: Random users (if we still need more)
        if len(potential_connections) < limit:
            logger.debug("Fetching random users to fill remaining slots")
            remaining_limit = limit - len(potential_connections)
            
            # Exclude users already added
            already_added_ids = {user["id"] for user in potential_connections}
            
            random_users_query = (
                select(User)
                .where(
                    and_(
                        *base_conditions,
                        ~User.id.in_(already_added_ids) if already_added_ids else True
                    )
                )
                .order_by(func.random())
                .limit(remaining_limit * 2)
            )
            
            result = await db.execute(random_users_query)
            random_users = result.scalars().all()
            
            for user in random_users:
                if len(potential_connections) >= limit:
                    break
                    
                user_dict = await _format_user_for_suggestions(user)
                potential_connections.append(user_dict)
            
            logger.debug(f"Added {len(random_users)} random users")
        
        logger.debug(f"Found {len(potential_connections)} total potential connections")
        
        return potential_connections
        
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_potential_connections: {str(e)}", exc_info=True)
        raise CustomHTTPException(500, "Failed to retrieve potential connections")
    except Exception as e:
        logger.error(f"Unexpected error in get_potential_connections: {str(e)}", exc_info=True)
        raise CustomHTTPException(500, "Failed to retrieve potential connections")


async def _format_user_for_suggestions(user: User) -> dict:
    """Helper function to format user data for connection suggestions"""
    return {
        "id": user.id,
        "full_name": user.full_name,
        "headline": user.bio,  # Use bio as headline since headline field doesn't exist
        "location": user.location,
        "pronouns": None,  # Field doesn't exist in User model
        "industry": user.industry,
        "years_of_experience": user.years_of_experience,
        "job_title": user.job_title,
        "profile_image_url": user.profile_image_url,
        "avatar_text": user.full_name[:2].upper() if user.full_name else None,  # Generate initials
        "recruiter_tag": user.recruiter_tag,
        "created_at": user.created_at,
        "connection_status": "none",  # These are filtered to only include non-connected users
        "action": "connect"
    }
