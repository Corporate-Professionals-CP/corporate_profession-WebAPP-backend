from pydantic import BaseModel

class JobTitleRead(BaseModel):
    id: int
    name: str

class JobTitleCreate(BaseModel):
    name: str

