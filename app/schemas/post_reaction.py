from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from app.models.post_reaction import ReactionType

class PostReactionCreate(BaseModel):
    post_id: str
    type: ReactionType

    class Config:
        use_enum_values = False

class PostReactionRead(BaseModel):
    user_id: str
    post_id: str
    type: ReactionType
    created_at: datetime

    class Config:
        orm_mode = True
        use_enum_values = False

