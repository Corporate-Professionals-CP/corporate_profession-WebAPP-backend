from sqlalchemy import Table, Column, String, ForeignKey
from app.db.database import Base

# Association table for many-to-many relationship
postskill = Table(
    "postskill",
    Base.metadata,
    Column("post_id", String, ForeignKey("post.id"), primary_key=True),
    Column("skill_id", String, ForeignKey("skill.id"), primary_key=True)
)
