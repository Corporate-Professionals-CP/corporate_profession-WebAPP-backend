from typing import List
from pydantic import BaseModel

class SkillBase(BaseModel):
    name: str

class SkillRead(SkillBase):
    id: int

class SkillUpdateRequest(BaseModel):
    skill_ids: List[int]

class SkillCreateRequest(BaseModel):
    names: List[str]

class SkillRead(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True
