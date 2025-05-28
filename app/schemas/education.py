from pydantic import BaseModel, HttpUrl, validator
from typing import Optional, Union
from datetime import date, datetime
from uuid import UUID

class EducationBase(BaseModel):
    degree: Optional[str] = None
    school: Optional[str] = None
    location: Optional[str] = None
    url: Optional[Union[str, HttpUrl]] = None
    description: Optional[str] = None
    media_url: Optional[Union[str, HttpUrl]] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None

    @validator('url', 'media_url', pre=True)
    def convert_httpurl_to_str(cls, v):
        if isinstance(v, HttpUrl):
            return str(v)
        return v

class EducationCreate(EducationBase):
    pass

class EducationUpdate(EducationBase):
    pass

class EducationRead(EducationBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True
