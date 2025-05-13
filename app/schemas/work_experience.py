from pydantic import BaseModel, HttpUrl,  validator
from typing import Optional, Union, List
from datetime import datetime
from app.schemas.enums import EmploymentType

class WorkExperienceBase(BaseModel):
    title: str
    company: str
    company_url: Optional[Union[str, HttpUrl]] = None
    location: str
    employment_type: EmploymentType
    start_date: datetime
    end_date: Optional[datetime] = None
    currently_working: bool = False
    description: Optional[str] = None
    achievements: Optional[str] = None

    @validator('company_url', pre=True)
    def convert_httpurl_to_str(cls, v):
        if isinstance(v, HttpUrl):
            return str(v)
        return v

class WorkExperienceCreate(WorkExperienceBase):
    pass

class WorkExperienceUpdate(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    company_url: Optional[Union[str, HttpUrl]] = None
    location: Optional[str] = None
    employment_type: Optional[EmploymentType] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    currently_working: Optional[bool] = None
    description: Optional[str] = None
    achievements: Optional[str] = None

    @validator('company_url', pre=True)
    def convert_httpurl_to_str(cls, v):
        if isinstance(v, HttpUrl):
            return str(v)
        return v

    @validator('start_date', 'end_date', pre=True)
    def remove_timezone(cls, v):
        if isinstance(v, datetime) and v.tzinfo is not None:
            return v.replace(tzinfo=None)
        return v

class WorkExperienceRead(WorkExperienceBase):
    id: str
    created_at: datetime

class WorkExperienceListResponse(BaseModel):
    data: List[WorkExperienceRead] = []

    class Config:
        orm_mode = True
