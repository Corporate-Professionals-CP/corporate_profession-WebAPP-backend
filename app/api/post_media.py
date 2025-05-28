from fastapi import APIRouter, UploadFile, File, Depends
from typing import List
from app.models.user import User
from app.core.security import get_current_active_user
from app.crud.post_media import upload_post_media_batch
from app.schemas.post_media import MediaUploadResponse

router = APIRouter(prefix="/media", tags=["media post"])

@router.post(
    "/media/batch",
    response_model=MediaUploadResponse,
    summary="Upload multiple media files for posts"
)
async def batch_upload_media(
    files: List[UploadFile] = File(...),  # Accepts multiple files
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload multiple images/videos for a post in one request.
    Returns URLs to use when creating the post.
    """
    urls = await upload_post_media_batch(
        user_id=str(current_user.id),
        files=files
    )
    return {"media_urls": urls}  # Returns array of URLs
