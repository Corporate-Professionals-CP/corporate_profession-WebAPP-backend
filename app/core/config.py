"""
Application configuration settings with enhanced security and validation.
Loads from environment variables with type checking.
"""

from pathlib import Path
from pydantic import AnyUrl, PostgresDsn, RedisDsn, validator
from pydantic_settings import BaseSettings
from typing import Optional, List

class Settings(BaseSettings):
    # Application Metadata
    PROJECT_TITLE: str = "Corporate Professionals WebApp API"
    PROJECT_DESCRIPTION: str = "Backend API for connecting corporate professionals and recruiters"
    PROJECT_VERSION: str = "1.0.0"
    OPENAPI_URL: str = "/openapi.json"
    DOCS_URL: str = "/docs"
    API_V1_STR: str = "/api/v1"

    # Database Configuration
    DATABASE_URL: PostgresDsn
    TEST_DATABASE_URL: Optional[PostgresDsn] = None

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
    GOOGLE_METADATA_URL: str = "https://accounts.google.com/.well-known/openid-configuration"

    # Email Service
    MAILJET_API_KEY: str
    MAILJET_SECRET_KEY: str
    VERIFICATION_EMAIL_TEMPLATE_ID: Optional[int] = None
    PASSWORD_RESET_TEMPLATE_ID: Optional[int] = None
    EMAILS_FROM_EMAIL: str
    EMAILS_FROM_NAME: str = "Corporate Professionals"

    # Cloudinary Configuration
    CLOUDINARY_CLOUD_NAME: str
    CLOUDINARY_API_KEY: str
    CLOUDINARY_API_SECRET: str
    CLOUDINARY_FOLDER: str = "cv_uploads"

    # Redis (for rate limiting)
    REDIS_URL: Optional[RedisDsn] = None

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [item.strip() for item in v.split(",")]
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True
        env_file_encoding = "utf-8"

settings = Settings()
