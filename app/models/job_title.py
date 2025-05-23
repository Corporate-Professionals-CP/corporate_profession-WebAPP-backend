from sqlmodel import SQLModel, Field
from typing import Optional

class JobTitle(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(..., max_length=100, unique=True)

