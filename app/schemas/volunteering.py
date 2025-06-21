from pydantic import BaseModel, HttpUrl, validator
from typing import Optional, Union
from datetime import datetime


class VolunteeringBase(BaseModel):
    role: str
    organization: str
    organization_url: Optional[Union[str, HttpUrl]] = None
    location: str
    start_date: datetime
    end_date: Optional[datetime] = None
    currently_volunteering: bool = False
    description: Optional[str] = None

    @validator('organization_url', pre=True)
    def convert_httpurl_to_str(cls, v):
        if isinstance(v, HttpUrl):
            return str(v)
        return v


class VolunteeringCreate(VolunteeringBase):
    pass


class VolunteeringUpdate(BaseModel):
    role: Optional[str] = None
    organization: Optional[str] = None
    organization_url: Optional[Union[str, HttpUrl]] = None
    location: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    currently_volunteering: Optional[bool] = None
    description: Optional[str] = None

    @validator('organization_url', pre=True)
    def convert_httpurl_to_str(cls, v):
        if isinstance(v, HttpUrl):
            return str(v)
        return v


class VolunteeringRead(VolunteeringBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True
