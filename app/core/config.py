"""
Application configuration settings with enhanced security and validation.
Loads from environment variables with type checking.
"""

from pathlib import Path
from pydantic import AnyUrl, PostgresDsn, RedisDsn, validator
from pydantic_settings import BaseSettings
from typing import Optional, List
import json
import base64

class Settings(BaseSettings):
    # Application Metadata
    PROJECT_TITLE: str = "Corporate Professionals WebApp API"
    PROJECT_DESCRIPTION: str = "Backend API for connecting corporate professionals and recruiters"
    PROJECT_VERSION: str = "1.0.0"
    OPENAPI_URL: str = "/openapi.json"
    DOCS_URL: str = "/docs"
    API_V1_STR: str = "/api/v1"
    PORT: int = None
    ENVIRONMENT: str

    # Database Configuration
    DATABASE_URL: PostgresDsn
    TEST_DATABASE_URL: Optional[PostgresDsn] = None
    FRONTEND_URL: AnyUrl 

    # Authentication
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = None
    REFRESH_TOKEN_EXPIRE_MINUTES: int = None

    # OAuth Providers
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str
    GOOGLE_AUTHORIZE_URL: str
    GOOGLE_ACCESS_TOKEN_URL: str
    GOOGLE_METADATA_URL: str
    GOOGLE_JWKS_URL: str
    GOOGLE_ISSUER: str

    #Google Cloud Storage Settings
    GCS_PROJECT_ID: str
    GCS_BUCKET_NAME: str
    GCS_BASE_PATH: str = "users/{user_id}/cvs"
    GCS_CREDENTIALS_JSON_B64: Optional[str] = None
    MAX_CV_SIZE: int = 5 * 1024 * 1024  # 5MB
    GCS_BASE_URL: str = "https://storage.googleapis.com"

    @property
    def GCS_PUBLIC_BASE_URL(self):
        return f"{self.GCS_BASE_URL}/{self.GCS_BUCKET_NAME}"

    GCS_PROFILE_IMAGE_BASE_PATH: str = "users/{user_id}/profile_images"
    MAX_PROFILE_IMAGE_SIZE: int = 5 * 1024 * 1024

    MAX_POST_MEDIA_SIZE: int = 50 * 1024 * 1024  # 50MB
    GCS_POST_MEDIA_BASE_PATH: str = "posts/{user_id}"

    # Email Service

    RESEND_API_KEY: str
    EMAILS_FROM_EMAIL: str
    EMAILS_FROM_NAME: str = "Corporate Professionals"
    ENVIRONMENT: str = "development"  # or 'testing', 'production'


    # Redis (for rate limiting)
    # REDIS_URL: Optional[RedisDsn] = None

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [item.strip() for item in v.split(",")]
        return v


    @validator("MAX_CV_SIZE")
    def validate_max_cv_size(cls, v):
        if v > 10 * 1024 * 1024:  # 10MB max
            raise ValueError("MAX_CV_SIZE cannot exceed 10MB")
        return v
        
    @property
    def GCS_CREDENTIALS_JSON(self) -> Optional[str]:
        """Decode base64 encoded credentials if available"""
        if self.GCS_CREDENTIALS_JSON_B64:
            try:
                return base64.b64decode(self.GCS_CREDENTIALS_JSON_B64).decode('utf-8')
            except Exception as e:
                raise ValueError(f"Failed to decode GCS credentials: {str(e)}")
        return None

    class Config:
        env_file = ".env"
        case_sensitive = True
        env_file_encoding = "utf-8"


settings = Settings()

