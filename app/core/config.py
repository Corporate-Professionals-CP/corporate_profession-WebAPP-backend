"""
Application configuration settings with enhanced security and validation.
Loads from environment variables with type checking.
"""

from pathlib import Path
from pydantic import AnyUrl, PostgresDsn, RedisDsn, validator
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Application Metadata
    PROJECT_TITLE: str = "Corporate Professionals WebApp API"
    PROJECT_DESCRIPTION: str = "Backend API for connecting corporate professionals and recruiters"
    PROJECT_VERSION: str = "1.0.0"
    OPENAPI_URL: str = "/openapi.json"
    DOCS_URL: str = "/docs"

    # Database Configuration
    DATABASE_URL: PostgresDsn
    TEST_DATABASE_URL: Optional[PostgresDsn] = None

    # Authentication
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 1 week
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30  # 30 days

    # OAuth Providers
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str

    # Email Service
    MAILJET_API_KEY: str
    MAILJET_SECRET_KEY: str
    VERIFICATION_EMAIL_TEMPLATE_ID: Optional[int] = None
    PASSWORD_RESET_TEMPLATE_ID: Optional[int] = None
    EMAILS_FROM_EMAIL: str
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 48

    # Cloudinary Configuration
    CLOUDINARY_CLOUD_NAME: str
    CLOUDINARY_API_KEY: str
    CLOUDINARY_API_SECRET: str
    CLOUDINARY_FOLDER: str = "cv_uploads"

    # Redis (for rate limiting)
    REDIS_URL: Optional[RedisDsn] = None

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["*"]

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
