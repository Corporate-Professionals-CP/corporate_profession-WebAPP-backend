from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID

class FollowingResponse(BaseModel):
    id: UUID
    username: str
    full_name: str
    bio: Optional[str]
    is_verified: bool
    is_following_you: bool
    mutual_followers_count: int
    latest_mutual_connections: List[str]

class FollowerResponse(BaseModel):
    id: UUID
    username: str
    full_name: str
    bio: Optional[str]
    is_verified: bool
    is_following: bool
    mutual_followers_count: int
    latest_mutual_connections: List[str]
