"""
Complete authentication schemas
security requirements
"""

from datetime import datetime
from pydantic import BaseModel

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

class EmailVerify(BaseModel):
    """Email verification request"""
    token: str

class PasswordReset(BaseModel):
    """Password reset request"""
    token: str
    new_password: str