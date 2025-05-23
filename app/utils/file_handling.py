import os
import json
from fastapi import HTTPException, UploadFile
from google.cloud import storage
from google.oauth2 import service_account
from app.core.config import settings
import magic
import logging
from datetime import datetime, timedelta
import base64
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Initialize GCS client
try:
    credentials = service_account.Credentials.from_service_account_info(
        json.loads(settings.GCS_CREDENTIALS_JSON)
    )
    storage_client = storage.Client(
        credentials=credentials,
        project=settings.GCS_PROJECT_ID
    )
    bucket = storage_client.bucket(settings.GCS_BUCKET_NAME)
except Exception as e:
    logger.error(f"Failed to initialize GCS client: {str(e)}")
    raise RuntimeError("Could not initialize cloud storage")

# File type configurations
CV_ALLOWED_MIME_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx"
}

PROFILE_IMAGE_ALLOWED_MIME_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif"
}

async def save_uploaded_file(file: UploadFile, user_id: str, file_type: str = "cv") -> str:
    """Upload file to Google Cloud Storage with validation"""
    try:
        # Determine settings based on file type
        if file_type == "cv":
            allowed_types = CV_ALLOWED_MIME_TYPES
            max_size = settings.MAX_CV_SIZE
            base_path = settings.GCS_BASE_PATH.format(user_id=user_id)
        elif file_type == "profile":
            allowed_types = PROFILE_IMAGE_ALLOWED_MIME_TYPES
            max_size = settings.MAX_PROFILE_IMAGE_SIZE
            base_path = settings.GCS_PROFILE_IMAGE_BASE_PATH.format(user_id=user_id)
        else:
            raise HTTPException(400, "Invalid file type specified")

        # Verify file type
        contents = await file.read(1024)
        mime_type = magic.from_buffer(contents, mime=True)
        await file.seek(0)

        if mime_type not in allowed_types:
            raise HTTPException(400, f"Only {', '.join(allowed_types.keys())} files allowed")

        # Verify file size
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)

        if file_size > max_size:
            raise HTTPException(400, f"File too large. Max size: {max_size//(1024*1024)}MB")

        # Generate unique filename
        file_ext = allowed_types[mime_type]
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{file_type}_{timestamp}.{file_ext}"
        blob_path = os.path.join(base_path, filename)

        # Upload to GCS
        blob = bucket.blob(blob_path)
        blob.upload_from_file(file.file, content_type=mime_type)

        return blob_path


    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload failed: {str(e)}")
        raise HTTPException(500, "Failed to process file upload")

async def delete_user_file(blob_reference: str) -> bool:
    try:
        # If input looks like a full URL, extract blob path from URL path
        if blob_reference.startswith("http"):
            parsed_url = urlparse(blob_reference)
            path_parts = parsed_url.path.lstrip('/').split('/')
            if len(path_parts) > 1:
                # Remove bucket name from path parts
                blob_path = '/'.join(path_parts[1:])
            else:
                return False
        else:
            # If already a blob path, use it as is
            blob_path = blob_reference

        logger.info(f"Deleting blob at path: {blob_path}")
        blob = bucket.blob(blob_path)

        if not blob.exists():
            logger.warning(f"Blob not found: {blob_path}")
            return False

        blob.delete()
        logger.info(f"Blob deleted: {blob_path}")
        return True
    except Exception as e:
        logger.error(f"File deletion failed: {str(e)}")
        return False

