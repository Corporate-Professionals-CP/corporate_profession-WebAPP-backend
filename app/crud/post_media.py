from fastapi import UploadFile, HTTPException
from app.utils.file_handling import save_uploaded_file
from typing import List
import logging

logger = logging.getLogger(__name__)

async def upload_post_media_batch(
    user_id: str, 
    files: List[UploadFile],
    max_files: int = 10  # Configurable limit
) -> List[str]:
    """Upload multiple media files for a post (matches CV/profile pattern but batched)"""
    if len(files) > max_files:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {max_files} files allowed per upload"
        )

    media_urls = []
    for file in files:
        try:
            url = await save_uploaded_file(
                file=file,
                user_id=user_id,
                file_type="post_media"  # Uses your existing file_handling logic
            )
            media_urls.append(url)
        except HTTPException as e:
            logger.error(f"Failed to upload {file.filename}: {e.detail}")
            raise HTTPException(
                status_code=e.status_code,
                detail=f"{file.filename}: {e.detail}"  # Forward specific errors
            )
        except Exception as e:
            logger.error(f"Unexpected error with {file.filename}: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process {file.filename}"
            )

    return media_urls
