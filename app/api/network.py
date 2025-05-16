from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from fastapi.responses import Response
from app.db.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.notification import Notification
from app.schemas.enums import NotificationType
from app.schemas.connection import ConnectionCreate, ConnectionUpdate, ConnectionRead
from app.crud.connection import (
    send_connection_request,
    respond_to_connection,
    get_my_requests,
    get_my_connections,
    remove_connection as crud_remove_connection
)
from app.crud.notification import create_notification
from app.utils.connection_helpers import format_connection
from app.core.exceptions import CustomHTTPException

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


@router.get("/pending", response_model=list[ConnectionRead])
async def pending_requests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        requests = await get_my_requests(db, str(current_user.id))
        return [format_connection(conn) for conn in requests]
    except Exception:
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

