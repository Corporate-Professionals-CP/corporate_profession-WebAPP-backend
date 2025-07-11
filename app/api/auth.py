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
from sqlalchemy import select
from app.db.database import get_db
from app.schemas.auth import (
    Token, EmailVerify, PasswordReset, 
    GoogleToken, UserCreateWithGoogle,
    SignupResponse, AuthResponse
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
from app.models.user import User
from starlette.status import *
from app.core.config import settings
from app.crud.user import get_user_by_email, create_user, update_user, get_user_by_id, get_user_by_email_or_username
from app.core.email import send_verification_email, send_password_reset_email
from pydantic import parse_obj_as
from sqlalchemy.orm.attributes import flag_modified
from app.core.exceptions import CustomHTTPException
from app.core.error_codes import (
    EMAIL_NOT_FOUND,
    NOT_AUTHORIZED,
    NOT_FOUND_ERROR,
    UNAUTHORIZED_ERROR,
    INVALID_CREDENTIALS,
    ACCOUNT_DEACTIVATION,
    ACCOUNT_NOT_VERIFIED,
    GOOGLE_EMAIL_NOT_VERIFIED,
    MISSING_GOOGLE_EMAIL,
    EMAIL_ALREADY_REGISTERED,
    INVALID_GOOGLE_TOKEN,
    EMAIL_ALREADY_VERIFIED,
    FAILED_TO_VERIFY_EMAIL,
    OTP_EXPIRED,
    NO_OTP_FOUND,
    GOOGLE_AUTH_FAILED,
    FAILED_TO_VERIFY_EMAIL,
    OTP_EXPIRED,
    PASSWORD_LENGTH,
    PASSWORD_MUST_NOT_THE_SAME,
    NO_OTP_FOUND,
    INVALID_OTP_FORMAT
)

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

@router.post("/token", response_model=AuthResponse)
@router.post("/login", response_model=AuthResponse)
async def login(
    request: Request,
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

    # Update login tracking
    user.last_login_at = datetime.utcnow()
    user.login_count += 1
    user.last_active_at = datetime.utcnow()
    
    # Store user ID and scopes before any commits to avoid lazy loading issues
    user_id = str(user.id)
    scopes = ["user"]
    if user.recruiter_tag:
        scopes.append("recruiter")
    if user.is_admin:
        scopes.append("admin")
    
    # Log the login activity
    try:
        from app.utils.activity_logger import log_user_activity
        await log_user_activity(
            db=db,
            user_id=user_id,
            activity_type="login",
            description="User logged in",
            ip_address=str(request.client.host) if request.client else None,
            user_agent=request.headers.get("user-agent"),
            extra_data={"login_method": "password"}
        )
    except Exception as e:
        logger.warning(f"Failed to log login activity: {e}")
    
    await db.commit()

    return {
        "access_token": create_access_token(user_id, scopes),
        "refresh_token": create_refresh_token(user_id),
        "token_type": "bearer",
        "expires_at": datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "user": user
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
            raise CustomHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
                error_code=EMAIL_ALREADY_REGISTERED
            )
        else:
            raise CustomHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This email was previously registered (account deactivated). Please contact support to reactivate.",
                error_code=ACCOUNT_DEACTIVATION
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

    # Send verification email with OTP
    if settings.ENVIRONMENT == "testing":
        otp = "123456"  # Fixed OTP for testing
        verification_data = {"verification_otp": otp}
    else:
        otp, _ = await send_verification_email(
            email=user.email,
            name=user.full_name,
            token=verification_token
        )
        verification_data = {}

    # Store OTP in user's profile_preferences (temporary storage)
    user.profile_preferences = user.profile_preferences or {}
    user.profile_preferences["email_verification_otp"] = otp
    user.profile_preferences["email_verification_token"] = verification_token
    user.profile_preferences["email_verification_expires"] = (datetime.utcnow() + timedelta(minutes=30)).isoformat()
    
    db.add(user)
    await db.commit()
    await db.refresh(user)

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
            raise CustomHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google email not verified",
                error_code=GOOGLE_EMAIL_NOT_VERIFIED
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
                error_code=GOOGLE_EMAIL_NOT_VERIFIED
            )

        # Extract email safely
        email = id_info.get("email")
        if not email:
            raise CustomHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google response missing email",
                error_code=MISSING_GOOGLE_EMAIL
            )

        # Check existing user
        existing_user = await get_user_by_email(db, email)
        if existing_user:
            raise CustomHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
                error_code=EMAIL_ALREADY_REGISTERED
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
            error_code=INVALID_GOOGLE_TOKEN
        )
    except Exception as e:
        logger.error(f"Google auth error: {str(e)}", exc_info=True)
        raise CustomHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google authentication failed: {str(e)}",
            error_code=GOOGLE_AUTH_FAILED
        )

@router.post("/verify-email", response_model=UserRead)
async def verify_email(
    verify: EmailVerify,
    db: AsyncSession = Depends(get_db)
):
    # Find all users with matching OTP in their profile_preferences
    stmt = select(User).where(
        User.profile_preferences["email_verification_otp"].as_string() == verify.otp
    )
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="Invalid OTP or user not found")

    # Check if already verified
    if user.is_verified:
        raise CustomHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified",
            error_code=EMAIL_ALREADY_VERIFIED
        )

    # Check OTP expiration
    prefs = user.profile_preferences or {}
    expires_at_str = prefs.get("email_verification_expires")

    if not expires_at_str or datetime.utcnow() > datetime.fromisoformat(expires_at_str):
        raise HTTPException(status_code=400, detail="OTP has expired")

    try:
        # Verify the stored token (not the one from request)
        stored_token = prefs.get("email_verification_token")
        if not stored_token:
            raise HTTPException(status_code=400, detail="Invalid verification")

        payload = verify_token(stored_token, expected_type="verify")
        if payload["sub"] != str(user.id):
            raise HTTPException(status_code=400, detail="Invalid verification")

        # Update user
        user.is_verified = True
        user.updated_at = datetime.utcnow()

        # Clean up OTP data
        if "email_verification_otp" in user.profile_preferences:
            del user.profile_preferences["email_verification_otp"]
            del user.profile_preferences["email_verification_token"]
            del user.profile_preferences["email_verification_expires"]

        db.add(user)
        await db.commit()
        await db.refresh(user)

        return user
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    except Exception as e:
        await db.rollback()
        raise CustomHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify email: {str(e)}",
            error_code=FAILED_TO_VERIFY_EMAIL
        )


@router.post("/resend-verification", status_code=status.HTTP_200_OK)
async def resend_verification(
    email: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db)
):
    user = await get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_verified:
        raise CustomHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified",
            error_code=EMAIL_ALREADY_VERIFIED
        )

    # Generate new token and OTP
    verification_token = create_access_token(
        user_id=str(user.id),
        expires_delta=timedelta(minutes=30),
        additional_claims={"type": "verify"}
    )

    # Generate and send OTP
    try:
        otp, _ = await send_verification_email(
            email=user.email,
            name=user.full_name,
            token=verification_token
        )
    except Exception as e:
        logger.error(f"Failed to send verification email: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to send verification email"
        )

    # Initialize profile_preferences if None
    if user.profile_preferences is None:
        user.profile_preferences = {}

    # Update verification data
    user.profile_preferences.update({
        "email_verification_otp": str(otp),  # Explicit string conversion
        "email_verification_token": verification_token,
        "email_verification_expires": (datetime.utcnow() + timedelta(minutes=30)).isoformat()
    })

    # Explicitly mark as modified for SQLAlchemy
    flag_modified(user, "profile_preferences")

    try:
        await db.commit()
        await db.refresh(user)
        logger.info(f"Verification OTP successfully stored for user {user.email}")
        logger.debug(f"Stored OTP: {user.profile_preferences.get('email_verification_otp')}")
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to store verification OTP: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process verification request"
        )

    return {"message": "Verification email resent"}

@router.post("/refresh-token", response_model=Token)
async def refresh_token(
    refresh_token: str = Body(...),
    db: AsyncSession = Depends(get_db)
):
    try:
        payload = verify_token(refresh_token, expected_type="refresh")
        user = await get_user_by_id(db, payload["sub"])
        if not user.is_active:
            raise CustomHTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated",
                error_code=ACCOUNT_DEACTIVATION
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



@router.post("/request-password-reset", status_code=status.HTTP_200_OK)
async def request_password_reset(
    email: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db)
):
    user = await get_user_by_email(db, email)
    if not user:
        return {"message": "If an account exists with this email, a reset OTP has been sent"}

    # Generate OTP
    otp = await send_password_reset_email(email=user.email, name=user.full_name)

    # Initialize profile_preferences if None
    if user.profile_preferences is None:
        user.profile_preferences = {}

    # Update OTP information
    user.profile_preferences.update({
        "password_reset_otp": str(otp),
        "password_reset_expires": (datetime.utcnow() + timedelta(minutes=30)).isoformat()
    })

    # Explicitly mark as modified for SQLAlchemy
    flag_modified(user, "profile_preferences")

    try:
        await db.commit()
        await db.refresh(user)  # Ensure we have the latest data
        logger.info(f"OTP successfully stored for user {user.email}")
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to store OTP: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process password reset request"
        )

    return {"message": "Password reset OTP sent"}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    reset: PasswordReset,
    db: AsyncSession = Depends(get_db)
):
    # Find user by email
    user = await get_user_by_email(db, reset.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Verify we have profile_preferences
    if not user.profile_preferences:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No OTP found for this user. Please request a new one."
        )

    # Get OTP data
    stored_otp = user.profile_preferences.get("password_reset_otp")
    expires_at_str = user.profile_preferences.get("password_reset_expires")

    # Debug logging
    logger.info(f"Stored OTP: {stored_otp}, Input OTP: {reset.otp}")
    logger.info(f"Full profile_preferences: {user.profile_preferences}")

    # Verify OTP exists and matches
    if not stored_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No OTP found for this user. Please request a new one."
        )

    if str(stored_otp).strip() != str(reset.otp).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP"
        )

    # Verify expiration
    try:
        expires_at = datetime.fromisoformat(expires_at_str) if expires_at_str else None
        if not expires_at or datetime.utcnow() > expires_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP has expired. Please request a new one."
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP expiration format"
        )

    # Password validation
    if len(reset.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters"
        )

    if verify_password(reset.new_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password cannot be the same as current password"
        )

    # Update password
    user.hashed_password = get_password_hash(reset.new_password)
    user.updated_at = datetime.utcnow()

    # Clear OTP data
    user.profile_preferences.pop("password_reset_otp", None)
    user.profile_preferences.pop("password_reset_expires", None)

    # Mark as modified
    flag_modified(user, "profile_preferences")

    try:
        await db.commit()
        await db.refresh(user)
        logger.info(f"Password successfully reset for user {user.email}")
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to reset password: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password"
        )

    return {"message": "Password updated successfully"}
