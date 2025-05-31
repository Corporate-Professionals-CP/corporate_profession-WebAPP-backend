import logging
from fastapi import APIRouter, Depends, status, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict
from app.db.database import get_db
from app.core.security import verify_token, get_user_by_id, get_current_active_user
from app.models.user import User
from app.models.notification import Notification
from app.schemas.notification import NotificationRead, NotificationResponse
from app.crud import notification as notif_crud
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
import json
from app.core.ws_manager import manager

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.websocket("/ws/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Secure WebSocket endpoint using existing token verification"""
    try:
        # Accept connection first (needed before sending errors)
        await websocket.accept()
        
        # Verify token using existing security function
        payload = verify_token(token, expected_type="access")
        user_id = payload["sub"]
        
        # Get user from database
        user = await get_user_by_id(db, user_id)
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # Check if user is active (optional)
        if not user.is_active:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
            
        # Register connection
        await manager.connect(websocket, str(user.id))
        
        # Connection maintenance loop
        while True:
            # Heartbeat handling
            data = await websocket.receive_text()
            if data != "ping":
                logger.warning(f"Unexpected WebSocket message: {data}")
                
    except HTTPException as e:
        logger.warning(f"WebSocket auth failed: {e.detail}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    except WebSocketDisconnect:
        if user:
            manager.disconnect(str(user.id))
            logger.info(f"User {user.id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)

@router.get("/", response_model=NotificationResponse)
async def get_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get notifications with current unread count"""
    user_id = str(current_user.id)
    return {
        "unread_count": await notif_crud.get_unread_notification_count(db, user_id),
        "notifications": await notif_crud.get_user_notifications(db, user_id)
    }

@router.put("/{notif_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notification_as_read(
    notif_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Mark notification as read and push count update"""
    success = await notif_crud.mark_as_read(db, notif_id, str(current_user.id))
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found or already read"
        )
