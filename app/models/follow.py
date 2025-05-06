from sqlalchemy import Column, ForeignKey, Integer
from sqlmodel import SQLModel, Field, Index


class UserFollow(SQLModel, table=True):
    """Join table for user following many-to-many relationship"""

    follower_id: str = Field(
        foreign_key="user.id",
        primary_key=True,
        index=True  # For faster follower queries
    )
    followed_id: str = Field(
        foreign_key="user.id",
        primary_key=True,
        index=True  # For faster followed queries
    )
