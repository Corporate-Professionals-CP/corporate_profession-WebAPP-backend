"""
Complete authentication endpoints
"""

from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import APIRouter, Depends, HTTPException, Request, status, Body
from fastapi.security import OAuth2PasswordRequestForm
from authlib.integrations.starlette_client import OAuth
from authlib.jose import JsonWebToken

from app.db.session import get_db
from app.schemas.auth import Token, TokenData, EmailVerify, PasswordReset
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_token
)
from app.core.config import settings
from app.crud.user import get_user_by_email, create_user, update_user, get_user_by_id

router = APIRouter(prefix="/auth", tags=["auth"])


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
if 'oauth' in locals():
    @router.get("/google/login")
    async def google_login(request: Request):
        """Initiate Google OAuth flow"""
        redirect_uri = request.url_for("google_callback")
        return await oauth.google.authorize_redirect(request, redirect_uri)

    @router.get("/google/callback", response_model=Token)
    async def google_callback(
        request: Request,
        db: AsyncSession = Depends(get_db)
    ):
        """Google OAuth flow"""
        try:
            token = await oauth.google.authorize_access_token(request)
            jwt = JsonWebToken.unsecure(token['id_token'])
            claims = jwt.decode()
            
            user_info = GoogleUserInfo(
                email=claims["email"],
                name=claims.get("name", ""),
                picture=claims.get("picture"),
                email_verified=claims.get("email_verified", False)
            )

            if not user_info.email_verified:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Google email not verified"
                )

            # Find or create user
            user = await get_user_by_email(db, user_info.email)
            if not user:
                user_data = {
                    "email": user_info.email,
                    "full_name": user_info.name,
                    "is_verified": True,
                    "hashed_password": get_password_hash(str(uuid.uuid4()))
                }
                user = await create_user(db, user_data)

            return {
                "access_token": create_access_token({"sub": str(user.id)}),
                "refresh_token": create_refresh_token({"sub": str(user.id)}),
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
    """Register new user with email verification"""
    existing_user = await get_user_by_email(db, user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "email_exists",
                "message": "Email already registered"
            }
        )

    user = await create_user(db, user_in)
    
    # Generate verification token
    verification_token = create_access_token(
        {"sub": str(user.id), "type": "verify"},
        timedelta(minutes=30)
    )
    
    # In production: Send email with verification_token
    print(f"Verification token: {verification_token}")
    
    return user

@router.post("/verify-email", response_model=UserRead)
async def verify_email(
    verify: EmailVerify,
    db: AsyncSession = Depends(get_db)
):
    """Complete email verification"""
    try:
        payload = verify_token(verify.token, expected_type="verify")
        user = await get_user_by_id(db, payload["sub"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        await update_user(db, user.id, {"is_verified": True})
        return user
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """Email/password login"""
    user = await get_user_by_email(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "invalid_credentials",
                "message": "Incorrect email or password"
            },
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return {
        "access_token": create_access_token({"sub": str(user.id)}),
        "refresh_token": create_refresh_token({"sub": str(user.id)}),
        "token_type": "bearer",
        "expires_at": datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    }

@router.post("/refresh-token", response_model=Token)
async def refresh_token(
    refresh_token: str = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token"""
    try:
        payload = verify_token(refresh_token, expected_type="refresh")
        user = await get_user_by_id(db, payload["sub"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "access_token": create_access_token({"sub": str(user.id)}),
            "refresh_token": create_refresh_token({"sub": str(user.id)}),
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
    """Initiate password reset"""
    user = await get_user_by_email(db, email)
    if user:
        reset_token = create_access_token(
            {"sub": str(user.id), "type": "reset"},
            timedelta(minutes=30)
        )
        # In production: Send email with reset_token
        print(f"Password reset token: {reset_token}")
    
    return {"message": "If email exists, reset instructions sent"}

@router.post("/reset-password")
async def reset_password(
    reset: PasswordReset,
    db: AsyncSession = Depends(get_db)
):
    """Complete password reset"""
    try:
        payload = verify_token(reset.token, expected_type="reset")
        user = await get_user_by_id(db, payload["sub"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        await update_user(db, user.id, {"hashed_password": get_password_hash(reset.new_password)})
        return {"message": "Password updated successfully"}
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired token")