from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime
from app.schemas.enums import ContactType

class ContactCreate(BaseModel):
    type: ContactType
    platform_name: Optional[str] = None
    username: Optional[str] = None
    url: str 

class ContactUpdate(BaseModel):
    platform_name: Optional[str]
    username: Optional[str]
    url: Optional[str]

class ContactRead(BaseModel):
    id: str
    type: ContactType
    platform_name: Optional[str]
    username: Optional[str]
    url: HttpUrl
    created_at: datetime

    class Config:
        orm_mode = True

