from app.models.connection import Connection
from app.schemas.connection import ConnectionRead, ConnectionUser

def format_connection(conn: Connection) -> ConnectionRead:
    try:
        sender_data = {
            "id": str(conn.sender.id),
            "full_name": conn.sender.full_name,
            "headline": getattr(conn.sender, "headline", None),
            "location": getattr(conn.sender, "location", None),
            "pronouns": getattr(conn.sender, "pronouns", None),
            "profile_image_url": (
            f"{conn.sender.profile_image_url}?v={int(conn.sender.profile_image_uploaded_at.timestamp())}"
            if getattr(conn.sender, "profile_image_url", None) and getattr(conn.sender, "profile_image_uploaded_at", None)
            else getattr(conn.sender, "profile_image_url", None)
        ),
            "avatar_text": getattr(conn.sender, "avatar_text", None),
            "recruiter_tag": getattr(conn.sender, "recruiter_tag", False),
            "created_at": conn.sender.created_at,
            "industry": getattr(conn.sender, "industry", None),
            "years_of_experience": getattr(conn.sender, "years_of_experience", None)
        }

        receiver_data = {
            "id": str(conn.receiver.id),
            "full_name": conn.receiver.full_name,
            "headline": getattr(conn.receiver, "headline", None),
            "location": getattr(conn.receiver, "location", None),
            "pronouns": getattr(conn.receiver, "pronouns", None),
            "profile_image_url": (
            f"{conn.receiver.profile_image_url}?v={int(conn.receiver.profile_image_uploaded_at.timestamp())}"
            if getattr(conn.receiver, "profile_image_url", None) and getattr(conn.receiver, "profile_image_uploaded_at", None)
            else getattr(conn.receiver, "profile_image_url", None)
        ),
            "avatar_text": getattr(conn.receiver, "avatar_text", None),
            "recruiter_tag": getattr(conn.receiver, "recruiter_tag", False),
            "created_at": conn.receiver.created_at,
            "industry": getattr(conn.receiver, "industry", None),
            "years_of_experience": getattr(conn.receiver, "years_of_experience", None)
        }

        return ConnectionRead(
            id=str(conn.id),
            sender_id=str(conn.sender_id),
            receiver_id=str(conn.receiver_id),
            status=conn.status,
            created_at=conn.created_at,
            sender=ConnectionUser(**sender_data),
            receiver=ConnectionUser(**receiver_data)
        )
    except Exception as e:
        raise
