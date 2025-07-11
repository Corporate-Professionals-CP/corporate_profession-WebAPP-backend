"""
Simple in-memory cache for user authentication
This will cache user objects for a short period to reduce database hits
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from app.models.user import User
from app.models.post import Post
from app.schemas.post import PostRead

class UserCache:
    def __init__(self, ttl_seconds: int = 300):  # 5 minutes default
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._ttl_seconds = ttl_seconds
    
    def _is_expired(self, cache_entry: Dict[str, Any]) -> bool:
        """Check if cache entry is expired"""
        return datetime.utcnow() > cache_entry["expires_at"]
    
    def get(self, user_id: str) -> Optional[User]:
        """Get user from cache if available and not expired"""
        if user_id in self._cache:
            entry = self._cache[user_id]
            if not self._is_expired(entry):
                return entry["user"]
            else:
                # Remove expired entry
                del self._cache[user_id]
        return None
    
    def set(self, user_id: str, user: User) -> None:
        """Cache user object"""
        self._cache[user_id] = {
            "user": user,
            "expires_at": datetime.utcnow() + timedelta(seconds=self._ttl_seconds)
        }
    
    def clear(self) -> None:
        """Clear all cached entries"""
        self._cache.clear()
    
    def remove(self, user_id: str) -> None:
        """Remove specific user from cache"""
        if user_id in self._cache:
            del self._cache[user_id]
    
    def cleanup_expired(self) -> None:
        """Remove expired entries from cache"""
        expired_keys = [
            key for key, entry in self._cache.items()
            if self._is_expired(entry)
        ]
        for key in expired_keys:
            del self._cache[key]

class FeedCache:
    def __init__(self, ttl_seconds: int = 180):  # 3 minutes for feed cache
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._ttl_seconds = ttl_seconds
    
    def _is_expired(self, cache_entry: Dict[str, Any]) -> bool:
        """Check if cache entry is expired"""
        return datetime.utcnow() > cache_entry["expires_at"]
    
    def get_feed(self, user_id: str, cache_key: str) -> Optional[List[PostRead]]:
        """Get cached feed for user"""
        key = f"feed:{user_id}:{cache_key}"
        if key in self._cache:
            entry = self._cache[key]
            if not self._is_expired(entry):
                return entry["posts"]
            else:
                del self._cache[key]
        return None
    
    def set_feed(self, user_id: str, cache_key: str, posts: List[PostRead]) -> None:
        """Cache feed for user"""
        key = f"feed:{user_id}:{cache_key}"
        self._cache[key] = {
            "posts": posts,
            "expires_at": datetime.utcnow() + timedelta(seconds=self._ttl_seconds)
        }
    
    def clear_user_feed(self, user_id: str) -> None:
        """Clear all feed cache for specific user"""
        keys_to_remove = [key for key in self._cache.keys() if key.startswith(f"feed:{user_id}:")]
        for key in keys_to_remove:
            del self._cache[key]
    
    def clear_all(self) -> None:
        """Clear all feed cache"""
        self._cache.clear()

# Global cache instance
user_cache = UserCache(ttl_seconds=300)  # 5 minutes
feed_cache = FeedCache(ttl_seconds=180)  # 3 minutes

async def start_cache_cleanup():
    """Background task to clean up expired cache entries"""
    while True:
        await asyncio.sleep(60)  # Run every minute
        user_cache.cleanup_expired()
