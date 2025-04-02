# app/utils/file_handling.py
import aiofiles
import magic
from fastapi import UploadFile, HTTPException
from pathlib import Path
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

async def save_uploaded_file(file: UploadFile, user_id: str) -> str:
    """Secure file upload handling with validation"""
    try:
        # Verify file type
        contents = await file.read(1024)
        mime_type = magic.from_buffer(contents, mime=True)
        await file.seek(0)
        
        if mime_type not in settings.ALLOWED_CV_TYPES:
            raise HTTPException(400, f"Only {', '.join(settings.ALLOWED_CV_TYPES)} files allowed")
        
        # Verify file size
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        
        if file_size > settings.MAX_CV_SIZE:
            raise HTTPException(400, f"File too large. Max size: {settings.MAX_CV_SIZE//(1024*1024)}MB")
        
        # Create user directory
        user_dir = settings.UPLOAD_DIR / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        
        # Save file
        ext = settings.ALLOWED_CV_TYPES[mime_type]
        file_path = user_dir / f"cv{ext}"
        
        async with aiofiles.open(file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                await buffer.write(chunk)
        
        return str(file_path.relative_to(settings.UPLOAD_DIR))
        
    except Exception as e:
        logger.error(f"File upload failed: {str(e)}")
        raise HTTPException(500, "Failed to process file upload")

async def delete_user_file(relative_path: str) -> bool:
    """Securely delete a user's file"""
    try:
        file_path = settings.UPLOAD_DIR / relative_path
        if file_path.exists():
            file_path.unlink()
        return True
    except Exception as e:
        logger.error(f"File deletion failed: {str(e)}")
        return False