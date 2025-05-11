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

logger = logging.getLogger(__name__)

# Initialize GCS client using environment variables
""
try:
    # Load credentials from environment variable
    credentials_info = json.loads(settings.GCS_CREDENTIALS_JSON)
    credentials = service_account.Credentials.from_service_account_info(credentials_info)
    
    storage_client = storage.Client(
        credentials=credentials,
        project=settings.GCS_PROJECT_ID
    )
    bucket = storage_client.bucket(settings.GCS_BUCKET_NAME)
except Exception as e:
    logger.error(f"Failed to initialize GCS client: {str(e)}")
    raise RuntimeError("Could not initialize cloud storage")


ALLOWED_MIME_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx"
}
""
async def save_uploaded_file(file: UploadFile, user_id: str) -> str:
    """Upload file to Google Cloud Storage with validation"""
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

        # Generate unique filename
        file_ext = ALLOWED_MIME_TYPES[mime_type]
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"cv_{user_id}_{timestamp}.{file_ext}"
        blob_path = os.path.join(settings.GCS_BASE_PATH, user_id, filename)

        # Upload to GCS
        blob = bucket.blob(blob_path)
        blob.upload_from_file(file.file, content_type=mime_type)
        
        # Generate signed URL for access
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=15),
            method="GET"
        )

        return url

    except Exception as e:
        logger.error(f"File upload failed: {str(e)}")
        raise HTTPException(500, "Failed to process file upload")

async def delete_user_file(url: str) -> bool:
    """Delete file from Google Cloud Storage"""
    try:
        # Extract blob path from URL
        base_url = f"https://storage.googleapis.com/{settings.GCS_BUCKET_NAME}/"
        blob_path = url.split(base_url)[1].split("?")[0]
        blob = bucket.blob(blob_path)
        
        if not blob.exists():
            return False
            
        blob.delete()
        return True
        
    except Exception as e:
        logger.error(f"File deletion failed: {str(e)}")
        return False
