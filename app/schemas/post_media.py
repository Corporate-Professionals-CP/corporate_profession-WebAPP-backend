from pydantic import BaseModel
from typing import List

class MediaUploadResponse(BaseModel):
    media_urls: List[str]  # Array of uploaded URLs
