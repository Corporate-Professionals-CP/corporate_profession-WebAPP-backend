import logging
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from fastapi.responses import Response
from app.db.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.notification import Notification
from app.schemas.enums import NotificationType
from app.schemas.connection import  ConnectionUser, ConnectionCreate, ConnectionUpdate, ConnectionRead
from app.crud.connection import (
    send_connection_request,
    respond_to_connection,
    get_my_requests,
    get_my_connections,
    get_pending_sent_requests,
    get_potential_connections,
    remove_connection as crud_remove_connection
)
from sqlalchemy.exc import SQLAlchemyError
from app.crud.notification import create_notification
from app.utils.connection_helpers import format_connection
from app.core.exceptions import CustomHTTPException


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)


formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)


logger.addHandler(ch)

router = APIRouter(prefix="/network", tags=["Connections"])


@router.post("/connect", response_model=ConnectionRead)
async def connect(
    payload: ConnectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        connection = await send_connection_request(
            db, str(current_user.id), str(payload.receiver_id)
        )

        if connection:
            await create_notification(
                db,
                Notification(
                    recipient_id=str(payload.receiver_id),
                    actor_id=str(current_user.id),
                    type=NotificationType.CONNECTION_REQUEST,
                    message=f"{current_user.full_name} sent you a connection request.",
                ),
            )

        return format_connection(connection)
    except CustomHTTPException:
        raise
    except Exception:
        raise CustomHTTPException(500, "Failed to send connection request")


@router.put("/{connection_id}/respond", response_model=ConnectionRead)
async def respond_to_request(
    connection_id: UUID,
    payload: ConnectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        conn = await respond_to_connection(db, str(connection_id), payload.status)

        if payload.status == "accepted":
            await create_notification(
                db,
                Notification(
                    recipient_id=str(conn.sender_id),
                    actor_id=str(current_user.id),
                    type=NotificationType.CONNECTION_ACCEPTED,
                    message=f"{current_user.full_name} accepted your connection request.",
                ),
            )

        return format_connection(conn)
    except CustomHTTPException:
        raise
    except Exception:
        raise CustomHTTPException(500, "Failed to respond to connection request")

@router.get("/pending", response_model=List[ConnectionRead])
async def pending_requests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        logger.debug(f"Fetching pending requests for user: {current_user.id}")
        
        requests = await get_my_requests(db, str(current_user.id))
        logger.debug(f"Retrieved {len(requests)} pending requests from database")
        
        if not requests:
            logger.info("No pending requests found")
            return []
        
        formatted = []
        for conn in requests:
            try:
                logger.debug(f"Formatting connection: {conn.id}")
                formatted_conn = format_connection(conn)
                formatted.append(formatted_conn)
                logger.debug(f"Successfully formatted connection: {conn.id}")
            except Exception as e:
                logger.error(f"Error formatting connection {conn.id}: {str(e)}", exc_info=True)
                continue
                
        logger.info(f"Successfully returned {len(formatted)} pending requests")
        return formatted
        
    except SQLAlchemyError as e:
        logger.error("Database error fetching pending requests:", exc_info=True)
        raise CustomHTTPException(500, "Failed to fetch pending connection requests")
    except Exception as e:
        logger.error("Unexpected error in pending_requests:", exc_info=True)
        raise CustomHTTPException(500, "Failed to fetch pending connection requests")

@router.get("/my-connections", response_model=list[ConnectionRead])
async def my_connections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        connections = await get_my_connections(db, str(current_user.id))
        return [format_connection(conn) for conn in connections]
    except Exception:
        raise CustomHTTPException(500, "Failed to fetch your connections")


@router.get("/sent-pending", response_model=list[ConnectionRead])
async def get_sent_pending_requests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all pending connection requests the current user has sent"""
    try:
        logger.info(f"Starting sent-pending request for user: {current_user.id}")
        
        requests = await get_pending_sent_requests(db, str(current_user.id))
        logger.debug(f"Retrieved {len(requests)} raw connection records")
        
        formatted_connections = []
        for conn in requests:
            try:
                logger.debug(f"Processing connection ID: {conn.id}")
                formatted = format_connection(conn)
                formatted_connections.append(formatted)
                logger.debug(f"Successfully formatted connection ID: {conn.id}")
            except Exception as e:
                logger.error(f"Failed to format connection ID: {conn.id}. Error: {str(e)}", 
                            exc_info=True)
                continue
        
        logger.info(f"Successfully processed {len(formatted_connections)} connections")
        return formatted_connections
        
    except CustomHTTPException:
        logger.error("Custom HTTP error in sent-pending endpoint", exc_info=True)
        raise
    except SQLAlchemyError as e:
        logger.error("Database error in sent-pending endpoint: "
                   f"User ID: {current_user.id}, Error: {str(e)}", exc_info=True)
        raise CustomHTTPException(500, "Failed to fetch sent pending connection requests")
    except Exception as e:
        logger.error("Unexpected error in sent-pending endpoint: "
                   f"User ID: {current_user.id}, Error: {str(e)}", exc_info=True)
        raise CustomHTTPException(500, "Failed to fetch sent pending connection requests")


@router.get("/suggestions", response_model=list[ConnectionUser])
async def get_connection_suggestions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 10
):
    """Get suggested connections for the current user"""
    try:
        logger.info(f"Starting connection suggestions for user {current_user.id}, limit {limit}")

        users = await get_potential_connections(db, str(current_user.id), limit)
        logger.debug(f"Retrieved {len(users)} potential users from database")

        suggestions = []
        for idx, user in enumerate(users, 1):
            try:
                logger.debug(f"Processing user {idx}/{len(users)}: {user.id}")

                suggestion = ConnectionUser(
                    id=str(user.id),
                    full_name=user.full_name,
                    headline=getattr(user, "headline", None),
                    location=getattr(user, "location", None),
                    pronouns=getattr(user, "pronouns", None),
                    industry=getattr(user, "industry", None),
                    years_of_experience=getattr(user, "years_of_experience", None),
                    job_title=getattr(user, "job_title", None),
                    profile_image_url=getattr(user, "profile_image_url", None),
                    avatar_text=getattr(user, "avatar_text", None),
                    recruiter_tag=getattr(user, "recruiter_tag", False),
                    created_at=user.created_at
                )
                suggestions.append(suggestion)
                logger.debug(f"Successfully processed user {user.id}")

            except Exception as e:
                logger.error(f"Failed to process user {user.id}: {str(e)}", exc_info=True)
                continue

        logger.info(f"Returning {len(suggestions)} connection suggestions")
        return suggestions

    except CustomHTTPException:
        logger.error("Custom HTTP error in suggestions endpoint", exc_info=True)
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error in suggestions endpoint: {str(e)}", exc_info=True)
        raise CustomHTTPException(500, "Failed to fetch connection suggestions")
    except Exception as e:
        logger.error(f"Unexpected error in suggestions endpoint: {str(e)}", exc_info=True)
        raise CustomHTTPException(500, "Failed to fetch connection suggestions")

@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_connection(
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        success = await crud_remove_connection(db, str(connection_id), str(current_user.id))
        if not success:
            raise CustomHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Connection not found or you don't have permission"
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except CustomHTTPException:
        raise
    except Exception:
        raise CustomHTTPException(500, "Failed to remove connection")


