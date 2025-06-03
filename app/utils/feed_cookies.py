from fastapi import Request, Response
from uuid import UUID
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

MAX_SEEN_POSTS = 100  # Keep last 100 posts to prevent cookie overflow
COOKIE_NAME = "seen_posts"

def track_seen_posts(response: Response, new_post_ids: List[UUID]):
    """Store seen post IDs in a cookie with corruption protection"""
    try:
        # Get existing IDs from request cookies (we'll pass them through)
        existing_cookie = response.headers.get("set-cookie", "")
        existing_ids = _parse_cookie_value(
            existing_cookie.split(f"{COOKIE_NAME}=")[-1].split(";")[0] 
            if COOKIE_NAME in existing_cookie 
            else ""
        )

        # Combine and deduplicate IDs
        all_ids = list(dict.fromkeys(
            [str(pid) for pid in (new_post_ids + existing_ids)]
        ))

        # Limit history size
        if len(all_ids) > MAX_SEEN_POSTS:
            all_ids = all_ids[:MAX_SEEN_POSTS]

        # Set updated cookie
        cookie_value = ",".join(all_ids)
        response.set_cookie(
            key=COOKIE_NAME,
            value=cookie_value,
            max_age=30 * 24 * 3600,  # 30 days
            httponly=True,
            secure=True,
            samesite="lax"
        )
    except Exception as e:
        logger.error(f"Failed to track seen posts: {str(e)}")
        # Reset cookie on failure
        response.delete_cookie(COOKIE_NAME)

def get_seen_posts_from_request(request: Request) -> List[UUID]:
    """Retrieve seen post IDs from cookie with corruption handling"""
    try:
        cookie_value = request.cookies.get(COOKIE_NAME, "")
        return _parse_cookie_value(cookie_value)
    except Exception as e:
        logger.warning(f"Invalid seen posts cookie: {str(e)}")
        return []

def _parse_cookie_value(value: str) -> List[UUID]:
    """Safely parse cookie value with validation"""
    if not value:
        return []

    cleaned = value.strip().strip(";")
    ids = []

    for part in cleaned.split(","):
        try:
            # Validate UUID format
            ids.append(UUID(part.strip()))
        except (ValueError, AttributeError):
            continue

    return ids
