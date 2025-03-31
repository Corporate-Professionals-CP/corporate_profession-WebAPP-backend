from pydantic import BaseSettings


class Settings(BaseSettings):
    PROJECT_TITLE: str = "Corporate Professionals WebApp API"
    PROJECT_DESCRIPTION: str = (
        "Backend API for connecting corporate professionals and recruiters."
    )
    PROJECT_VERSION: str = "1.0.0"
    OPENAPI_URL: str = "/openapi.json"
    DATABASE_URL: str

    # Google OAuth2 Settings
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str
    GOOGLE_AUTHORIZE_URL: str
    GOOGLE_ACCESS_TOKEN_URL: str

    # Email Configuration
    MAILJET_API_KEY: str
    MAILJET_SECRET_KEY: str
    MAIL_FROM: str
    MAIL_FROM_NAME: str
    
    # JWT Token Settings
    SECRET_KEY: str
    JWT_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    class Config:
        env_file = ".env"


settings = Settings()

