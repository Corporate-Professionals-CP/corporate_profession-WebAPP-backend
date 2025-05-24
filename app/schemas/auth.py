from datetime import datetime
from pydantic import BaseModel, EmailStr
from typing import Optional
from app.schemas.user import UserRead

class Token(BaseModel):
    """Complete token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: datetime

class TokenData(BaseModel):
    """Decoded token payload"""
    user_id: str
    type: Optional[str] = None  # 'verify' or 'reset'
    scopes: list[str] = []

class EmailVerify(BaseModel):
    """Email verification request"""
    otp: str
    email: Optional[str] = None
    token: Optional[str] = None

class PasswordReset(BaseModel):
    """Password reset request"""
    token: str
    new_password: str

class GoogleToken(BaseModel):
    """Google OAuth token response"""
    id_token: str

class UserCreateWithGoogle(BaseModel):
    """User creation schema for Google OAuth"""
    google_token: str
    recruiter_tag: bool = False

class SignupResponse(BaseModel):
    access_token: str
    refresh_token: str
    user_id: str
    user: UserRead
