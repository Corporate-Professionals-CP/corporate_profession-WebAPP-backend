from app.models.connection import Connection
from app.schemas.connection import ConnectionRead, ConnectionUser
from app.schemas.user import UserPublic

def format_connection(conn: Connection) -> ConnectionRead:
    return ConnectionRead(
        id=str(conn.id),
        sender_id=str(conn.sender_id),
        receiver_id=str(conn.receiver_id),
        status=conn.status,
        created_at=conn.created_at,
        sender=ConnectionUser(
            id=str(conn.sender.id),
            full_name=conn.sender.full_name,
        ),
        receiver=ConnectionUser(
            id=str(conn.receiver.id),
            full_name=conn.receiver.full_name,
        ),
    )
