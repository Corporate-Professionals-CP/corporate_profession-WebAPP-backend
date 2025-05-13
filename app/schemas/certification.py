from pydantic import BaseModel, HttpUrl, validator
from typing import Optional, Union
from datetime import date, datetime
from uuid import UUID

class CertificationBase(BaseModel):
    name: Optional[str] = None
    organization: Optional[str] = None
    url: Optional[Union[str, HttpUrl]] = None
    description: Optional[str] = None
    media_url: Optional[Union[str, HttpUrl]] = None
    issued_date: Optional[date] = None
    expiration_date: Optional[date] = None

    @validator('url', 'media_url', pre=True)
    def convert_httpurl_to_str(cls, v):
        if isinstance(v, HttpUrl):
            return str(v)
        return v

class CertificationCreate(CertificationBase):
    pass

class CertificationUpdate(CertificationBase):
    pass

class CertificationRead(CertificationBase):
    id: UUID
    created_at: datetime

    class Config:
        orm_mode = True
