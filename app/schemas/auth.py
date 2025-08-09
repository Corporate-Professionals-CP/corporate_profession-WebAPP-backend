from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
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
    email: str
    otp: str
    new_password: str

class GoogleToken(BaseModel):
    """Google OAuth token response"""
    id_token: str

class UserCreateWithGoogle(BaseModel):
    """User creation schema for Google OAuth"""
    google_token: str
    recruiter_tag: bool = False
    skills: Optional[List[int]] = Field(
        default_factory=list,
        description="List of skill IDs to associate with the user during signup"
    )

class SignupResponse(BaseModel):
    access_token: str
    refresh_token: str
    user_id: str
    user: UserRead

class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserRead

