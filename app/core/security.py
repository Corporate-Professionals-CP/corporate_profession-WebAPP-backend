from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from fastapi import Depends, HTTPException, status, Security
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.models.user import User
from app.db.database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme with scopes
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/token",
    scopes={
        "user": "Regular user access",
        "recruiter": "Recruiter privileges",
        "moderator": "Moderator privileges",
        "admin": "Admin privileges"
    }
)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_token(
    user_id: str,
    token_type: str,
    expires_delta: Optional[timedelta] = None,
    scopes: Optional[list[str]] = None,
    additional_claims: Optional[Dict[str, Any]] = None
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES if token_type == "access" else settings.REFRESH_TOKEN_EXPIRE_MINUTES
    ))

    payload = {
        "sub": str(user_id),
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "type": token_type,
    }

    if token_type == "access":
        payload["scopes"] = scopes or ["user"]

    if additional_claims:
        payload.update(additional_claims)

    try:
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error encoding JWT: {str(e)}"
        )

def create_access_token(
    user_id: str,
    scopes: Optional[list[str]] = None,
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[Dict[str, Any]] = None
) -> str:
    return create_token(user_id, "access", expires_delta, scopes, additional_claims)

def create_refresh_token(
    user_id: str,
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[Dict[str, Any]] = None
) -> str:
    return create_token(user_id, "refresh", expires_delta, None, additional_claims)

def verify_token(token: str, expected_type: Optional[str] = None) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        if expected_type and payload.get("type") != expected_type:
            raise JWTError("Invalid token type")
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    """Get user by ID - optimized with caching"""
    from app.utils.cache import user_cache
    
    # Try cache first
    cached_user = user_cache.get(user_id)
    if cached_user:
        return cached_user
    
    # If not in cache, query database
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalars().first()
    
    # Cache the result if user found
    if user:
        user_cache.set(user_id, user)
    
    return user

async def get_current_user(
    security_scopes: SecurityScopes,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
    else:
        authenticate_value = "Bearer"

    payload = verify_token(token, expected_type="access")
    user = await get_user_by_id(db, user_id=payload["sub"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
            headers={"WWW-Authenticate": authenticate_value},
        )

    token_scopes = payload.get("scopes", [])
    for scope in security_scopes.scopes:
        if scope not in token_scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
                headers={"WWW-Authenticate": authenticate_value},
            )

    return user

async def get_current_active_user(
    current_user: User = Security(get_current_user, scopes=["user"])
) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user

async def get_recruiter_user(
    current_user: User = Security(get_current_user, scopes=["recruiter"])
) -> User:
    if not current_user.recruiter_tag:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Recruiter privileges required"
        )
    return current_user

async def get_moderator_user(
    current_user: User = Security(get_current_user, scopes=["moderator"])
) -> User:
    if not current_user.is_moderator and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Moderator privileges required"
        )
    return current_user

async def get_admin_user(
    current_user: User = Security(get_current_user, scopes=["admin"])
) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user

async def get_current_active_admin(
    current_user: User = Security(get_current_user, scopes=["admin"])
) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user

