import cloudinary
import cloudinary.uploader
from fastapi import HTTPException, UploadFile
from app.core.config import settings
import magic
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Configure Cloudinary
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)

ALLOWED_MIME_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx"
}

async def save_uploaded_file(file: UploadFile, user_id: str) -> str:
    """Upload file to Cloudinary with validation"""
    try:
        # Verify file type
        contents = await file.read(1024)
        mime_type = magic.from_buffer(contents, mime=True)
        await file.seek(0)
        
        if mime_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(400, f"Only {', '.join(ALLOWED_MIME_TYPES.keys())} files allowed")

        # Verify file size
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        
        if file_size > settings.MAX_CV_SIZE:
            raise HTTPException(400, f"File too large. Max size: {settings.MAX_CV_SIZE//(1024*1024)}MB")

        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            file.file,
            folder=f"{settings.CLOUDINARY_FOLDER}/{user_id}",
            resource_type="auto"
        )
        
        return upload_result["secure_url"]

    except Exception as e:
        logger.error(f"File upload failed: {str(e)}")
        raise HTTPException(500, "Failed to process file upload")

async def delete_user_file(public_url: str) -> bool:
    """Delete file from Cloudinary"""
    try:
        # Extract public ID from URL
        public_id = public_url.split("/")[-1].split(".")[0]
        result = cloudinary.uploader.destroy(public_id)
        return result.get('result') == 'ok'
    except Exception as e:
        logger.error(f"File deletion failed: {str(e)}")
        return False
