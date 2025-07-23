from pydantic import BaseModel, HttpUrl, validator
from typing import Optional, Union
from datetime import datetime
from app.schemas.enums import ContactType

class ContactCreate(BaseModel):
    type: ContactType
    platform_name: Optional[str] = None
    username: Optional[str] = None
    url:  Optional[Union[str, HttpUrl]] = None

    @validator('url', pre=True)
    def convert_httpurl_to_str(cls, v):
        if isinstance(v, HttpUrl):
            return str(v)
        return v

class ContactUpdate(BaseModel):
    platform_name: Optional[str]
    username: Optional[str]
    url:  Optional[Union[str, HttpUrl]] = None

    @validator('url', pre=True)
    def convert_httpurl_to_str(cls, v):
        if isinstance(v, HttpUrl):
            return str(v)
        return v

class ContactRead(BaseModel):
    id: str
    type: ContactType
    platform_name: Optional[str]
    username: Optional[str]
    url:  Optional[Union[str, HttpUrl]] = None
    created_at: datetime

    @validator('url', pre=True)
    def convert_httpurl_to_str(cls, v):
        if isinstance(v, HttpUrl):
            return str(v)
        return v

    class Config:
        from_attributes = True
