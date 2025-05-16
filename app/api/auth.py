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
import requests
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from app.db.database import get_db
from app.schemas.auth import (
    Token, EmailVerify, PasswordReset, 
    GoogleToken, UserCreateWithGoogle,
    SignupResponse
)
from app.schemas.user import UserRead, UserCreate, UserUpdate
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_token,
    get_current_user
)
from starlette.status import *
from app.core.config import settings
from app.crud.user import get_user_by_email, create_user, update_user, get_user_by_id, get_user_by_email_or_username
from app.core.email import send_verification_email, send_password_reset_email
from pydantic import parse_obj_as
from app.core.error_codes import (
    EMAIL_NOT_FOUND,
    NOT_AUTHORIZED,
    NOT_FOUND_ERROR,
    UNAUTHORIZED_ERROR,
    INVALID_CREDENTIALS,
    ACCOUNT_DEACTIVATION,
    GOOGLE_EMAIL_NOT_VERIFIED,
    MISSING_GOOGLE_EMAIL,
    EMAIL_ALREADY_REGISTERED,
    INVALID_GOOGLE_TOKEN,
    GOOGLE_AUTH_FAILED
)


from app.core.exceptions import CustomHTTPException

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
    user = await get_user_by_email(db, form_data.username)
    if not user:
        logger.warning(f"Login attempt for non-existent user: {form_data.username}")
        raise CustomHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email not found",
            error_code=EMAIL_NOT_FOUND,
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(form_data.password, user.hashed_password):
        logger.warning(f"Failed login attempt for user: {user.email}")
        raise CustomHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            error_code=INVALID_CREDENTIALS,
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise CustomHTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account deactivated. Please contact support",
            error_code=ACCOUNT_DEACTIVATION,
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_verified:
        raise CustomHTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not verified. Please check your email",
            error_code=ACCOUNT_NOT_VERIFIED,
            headers={"WWW-Authenticate": "Bearer"},
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


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    request: Request,
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Email/password signup with verification"""
    existing_user = await get_user_by_email(db, user_in.email)

    if existing_user:
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

    # Create new user
    user = await create_user(db, user_in)

    # Generate tokens
    access_token = create_access_token(user_id=str(user.id))
    refresh_token = create_refresh_token(user_id=str(user.id))
    verification_token = create_access_token(
        user_id=str(user.id),
        expires_delta=timedelta(minutes=30),
        additional_claims={"type": "verify"}
    )

    # For testing, include verification token in response
    if settings.ENVIRONMENT == "testing":
        logger.info(f"Verification token for {user.email}: {verification_token}")
        verification_data = {"verification_token": verification_token}
    else:
        verification_data = {}
        await send_verification_email(
            email=user.email,
            name=user.full_name,
            token=verification_token
        )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user_id": str(user.id),
        "user": user,
        **verification_data
    }

@router.post("/google", response_model=Token)
async def google_oauth(
    google_data: GoogleToken,
    db: AsyncSession = Depends(get_db)
):
    try:
        id_info = id_token.verify_oauth2_token(
            google_data.id_token,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID
        )

        if not id_info.get("email_verified", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google email not verified"
            )

        user = await get_user_by_email(db, id_info["email"])
        if not user:
            user_data = {
                "email": id_info["email"],
                "full_name": id_info.get("name", ""),
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

@router.post("/signup/google", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup_with_google(
    user_in: UserCreateWithGoogle,
    db: AsyncSession = Depends(get_db)
):
    """Google OAuth signup using google-auth library"""
    try:
        # Verify the token using Google's API
        id_info = id_token.verify_oauth2_token(
            user_in.google_token,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID
        )

        # Log the full Google response for debugging
        logger.info(f"Google ID Info: {id_info}")

        # Validate required claims
        if id_info.get('iss') not in ['accounts.google.com', 'https://accounts.google.com']:
            raise ValueError("Wrong issuer")

        # Check email verification
        if not id_info.get('email_verified', False):
            raise CustomHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google email not verified",
                error_code="GOOGLE_EMAIL_NOT_VERIFIED"
            )

        # Extract email safely
        email = id_info.get("email")
        if not email:
            raise CustomHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google response missing email",
                error_code="MISSING_GOOGLE_EMAIL"
            )

        # Check existing user
        existing_user = await get_user_by_email(db, email)
        if existing_user:
            raise CustomHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
                error_code="EMAIL_ALREADY_REGISTERED"
            )

        # Create user data
        user_data = {
            "email": email,
            "full_name": id_info.get("name", ""),
            "is_verified": True,
            "hashed_password": get_password_hash(str(uuid.uuid4())),
            "recruiter_tag": user_in.recruiter_tag
        }
        user = await create_user(db, user_data)

        # Generate tokens (same as regular signup)
        access_token = create_access_token(user_id=str(user.id))
        refresh_token = create_refresh_token(user_id=str(user.id))

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_id": str(user.id),
            "user": user
        }

    except ValueError as e:
        raise CustomHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Google token: {str(e)}",
            error_code="INVALID_GOOGLE_TOKEN"
        )
    except Exception as e:
        logger.error(f"Google auth error: {str(e)}", exc_info=True)
        raise CustomHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google authentication failed: {str(e)}",
            error_code="GOOGLE_AUTH_FAILED"
        )


@router.post("/verify-email", response_model=UserRead)
async def verify_email(
    verify: EmailVerify,
    db: AsyncSession = Depends(get_db)
):
    try:
        # Verify token and get user
        payload = verify_token(verify.token, expected_type="verify")
        user = await get_user_by_id(db, payload["sub"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if already verified
        if user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already verified"
            )

        # Directly update the verification status
        user.is_verified = True
        user.updated_at = datetime.utcnow()
        
        try:
            db.add(user)
            await db.commit()
            await db.refresh(user)
            
            # Return the updated user
            return user
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to verify email: {str(e)}"
            )

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
            user_id=str(user.id),
            expires_delta=timedelta(minutes=30),
            additional_claims={"type": "reset"}
        )

        # Add this logging statement
        logger.info(f"Password reset token for {email}: {reset_token}")

        await send_password_reset_email(
            email=user.email,
            name=user.full_name,
            token=reset_token
        )
    return {"message": "Check your email, reset instructions sent"}


@router.post("/reset-password")
async def reset_password(
    reset: PasswordReset,
    db: AsyncSession = Depends(get_db)
):
    try:
        # Validate token structure
        if not reset.token or len(reset.token.split('.')) != 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token format"
            )

        # Validate password
        if len(reset.new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters"
            )

        # Verify token
        payload = verify_token(reset.token, expected_type="reset")
        user = await get_user_by_id(db, payload["sub"])
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Check password reuse
        if verify_password(reset.new_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password cannot be the same as current password"
            )

        # Prepare update data (plain dict, no .dict() calls)
        update_data = {
            "hashed_password": get_password_hash(reset.new_password),
            "updated_at": datetime.utcnow()  # Add timestamp update
        }

        # Perform update
        await update_user(db, user.id, update_data)
        
        logger.info(f"Password reset successful for user {user.email}")
        return {"message": "Password updated successfully"}

    except JWTError as e:
        logger.error(f"Token verification failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during password reset: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
