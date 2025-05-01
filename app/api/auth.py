"""
Complete authentication endpoints
"""

import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Body, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt
from authlib.integrations.starlette_client import OAuth
from authlib.jose import JsonWebToken
import uuid

from app.db.database import get_db
from app.schemas.auth import (
    Token, EmailVerify, PasswordReset, 
    GoogleToken, UserCreateWithGoogle
)
from app.schemas.user import UserRead, UserCreate
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_token,
    get_current_user
)
from app.core.config import settings
from app.crud.user import get_user_by_email, create_user, update_user, get_user_by_id, get_user_by_email_or_username
from app.core.email import send_verification_email, send_password_reset_email


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


handler = logging.StreamHandler()
handler.setLevel(logging.INFO)


formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
handler.setFormatter(formatter)


logger.addHandler(handler)


router = APIRouter(prefix="/auth", tags=["Authentication"])

# Initialize Google OAuth if configured
oauth = None
if all([settings.GOOGLE_CLIENT_ID, settings.GOOGLE_CLIENT_SECRET]):
    oauth = OAuth()
    oauth.register(
        name="google",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        authorize_url=settings.GOOGLE_AUTHORIZE_URL,
        access_token_url=settings.GOOGLE_ACCESS_TOKEN_URL,
        client_kwargs={"scope": "openid email profile"},
        server_metadata_url=settings.GOOGLE_METADATA_URL
    )

@router.post("/token", response_model=Token)
@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    try:
        user = await get_user_by_email_or_username(db, form_data.username)
        if not user:
            logger.warning(f"Login attempt for non-existent user: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not verify_password(form_data.password, user.hashed_password):
            logger.warning(f"Failed login attempt for user: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )


        if not user.is_active:
            logger.warning(f"Login attempt for deactivated account: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account deactivated. Please contact support.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        #if not user.is_verified:
        #    logger.info(f"Login attempt for unverified account: {user.email}")
        #    raise HTTPException(
        #        status_code=status.HTTP_403_FORBIDDEN,
        #        detail="Account not verified. Please check your email.",
        #        headers={"WWW-Authenticate": "Bearer"},
        #    )

        scopes = ["user"]
        if user.recruiter_tag:
            scopes.append("recruiter")
        if user.is_admin:
            scopes.append("admin")

        return {
            "access_token": create_access_token(user.id, scopes),
            "refresh_token": create_refresh_token(user.id),
            "token_type": "bearer",
            "expires_at": datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        }
    except Exception as e:
        import traceback
        print("\n AUTH ERROR on /token:")
        print(f"Exception: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/google", response_model=Token)
async def google_oauth(
    google_data: GoogleToken,
    db: AsyncSession = Depends(get_db)
):
    """Google OAuth login endpoint"""
    if not oauth:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth not configured"
        )

    try:
        jwt_token = JsonWebToken.unsecure(google_data.id_token)
        claims = jwt_token.decode()
        
        if not claims.get("email_verified", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google email not verified"
            )

        # Find or create user
        user = await get_user_by_email(db, claims["email"])
        if not user:
            user_data = {
                "email": claims["email"],
                "full_name": claims.get("name", ""),
                "is_verified": True,
                "hashed_password": get_password_hash(str(uuid.uuid4()))
            }
            user = await create_user(db, user_data)

        scopes = ["user"]
        if user.recruiter_tag:
            scopes.append("recruiter")
        if user.is_admin:
            scopes.append("admin")

        return {
            "access_token": create_access_token(user.id, scopes),
            "refresh_token": create_refresh_token(user.id),
            "token_type": "bearer",
            "expires_at": datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google authentication failed: {str(e)}"
        )

@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def signup(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Email/password signup"""
    existing_user = await get_user_by_email(db, user_in.email)
    if existing_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This email was previously registered (account deactivated). Please contact support to reactivate."
            )

    user = await create_user(db, user_in)
    verification_token = create_access_token(
    user_id=str(user.id),
    expires_delta=timedelta(minutes=30),
    additional_claims={"type": "verify"}
)
    
    await send_verification_email(
        email=user.email,
        name=user.full_name,
        token=verification_token
    )
    return user

@router.post("/signup/google", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def signup_with_google(
    user_in: UserCreateWithGoogle,
    db: AsyncSession = Depends(get_db)
):
    """Google OAuth signup"""
    if not oauth:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth not configured"
        )

    try:
        jwt_token = JsonWebToken.unsecure(user_in.google_token)
        claims = jwt_token.decode()
        
        if not claims.get("email_verified", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google email not verified"
            )

        existing_user = await get_user_by_email(db, claims["email"])
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        user_data = {
            "email": claims["email"],
            "full_name": claims.get("name", ""),
            "is_verified": True,
            "hashed_password": get_password_hash(str(uuid.uuid4())),
            "recruiter_tag": user_in.recruiter_tag
        }
        user = await create_user(db, user_data)
        return user

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google authentication failed: {str(e)}"
        )

@router.post("/verify-email", response_model=UserRead)
async def verify_email(
    verify: EmailVerify,
    db: AsyncSession = Depends(get_db)
):
    try:
        payload = verify_token(verify.token, expected_type="verify")
        user = await get_user_by_id(db, payload["sub"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        await update_user(db, user.id, {"is_verified": True})
        return user
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

@router.post("/refresh-token", response_model=Token)
async def refresh_token(
    refresh_token: str = Body(...),
    db: AsyncSession = Depends(get_db)
):
    try:
        payload = verify_token(refresh_token, expected_type="refresh")
        user = await get_user_by_id(db, payload["sub"])
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated"
            )

        scopes = ["user"]
        if user.recruiter_tag:
            scopes.append("recruiter")
        if user.is_admin:
            scopes.append("admin")

        return {
            "access_token": create_access_token(user.id, scopes),
            "refresh_token": create_refresh_token(user.id),
            "token_type": "bearer",
            "expires_at": datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        }
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

@router.post("/forgot-password")
async def forgot_password(
    email: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db)
):
    user = await get_user_by_email(db, email)
    if user:
        reset_token = create_access_token(
            {"sub": str(user.id), "type": "reset"},
            timedelta(minutes=30)
        )
        await send_password_reset_email(
            email=user.email,
            name=user.full_name,
            token=reset_token
        )
    return {"message": "If email exists, reset instructions sent"}

@router.post("/reset-password")
async def reset_password(
    reset: PasswordReset,
    db: AsyncSession = Depends(get_db)
):
    try:
        payload = verify_token(reset.token, expected_type="reset")
        user = await get_user_by_id(db, payload["sub"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        await update_user(db, user.id, {"hashed_password": get_password_hash(reset.new_password)})
        return {"message": "Password updated successfully"}
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
