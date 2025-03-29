from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status, Body
from sqlmodel import Session
from authlib.integrations.starlette_client import OAuth

from app.db.database import get_session
from app.crud.user import get_user_by_email, create_user, update_user
from app.schemas.auth import Token
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import hash_password, verify_password, create_access_token
from app.core.config import settings

router = APIRouter()

# In-memory token stores (for demonstration purposes)
email_verification_tokens = {}
password_reset_tokens = {}


@router.post("/signup", response_model=dict, status_code=status.HTTP_201_CREATED)
def signup(user: UserCreate, session: Session = Depends(get_session)):
    """
    Create a new user account and initiate email verification.
    """
    existing_user = get_user_by_email(session, user.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Hash the password before storing
    user.password = hash_password(user.password)
    new_user = create_user(session, user)
    
    # Generate an email verification token (simulate; in production, send via email)
    verification_token = create_access_token(
        {"email": new_user.email}, expires_delta=timedelta(minutes=30)
    )
    email_verification_tokens[new_user.email] = verification_token
    print(f"[DEBUG] Verification token for {new_user.email}: {verification_token}")
    
    return {"message": "User created. Please verify your email."}

@router.post("/verify-email", status_code=status.HTTP_200_OK)
def verify_email(email: str = Body(...), token: str = Body(...), session: Session = Depends(get_session)):
    """
    Verify a user's email address using the provided token.
    """
    expected_token = email_verification_tokens.get(email)
    if not expected_token or expected_token != token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification token"
        )
    
    db_user = get_user_by_email(session, email)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Here, update the user record to mark the email as verified.
    user_update = UserUpdate()
    # Example: user_update.is_verified = True
    # For now, we'll assume verification is complete and remove the token.
    del email_verification_tokens[email]
    
    return {"message": "Email verified successfully"}

@router.post("/login", response_model=Token)
def login(email: str = Body(...), password: str = Body(...), session: Session = Depends(get_session)):
    """
    Authenticate a user using email and password, and return a JWT token.
    """
    db_user = get_user_by_email(session, email)
    if not db_user or not verify_password(password, db_user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    access_token = create_access_token({"sub": db_user.id})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(email: str = Body(...), session: Session = Depends(get_session)):
    """
    Initiate password recovery by generating a reset token.
    """
    db_user = get_user_by_email(session, email)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    reset_token = create_access_token({"sub": db_user.id}, expires_delta=timedelta(minutes=30))
    password_reset_tokens[email] = reset_token
    print(f"[DEBUG] Password reset token for {email}: {reset_token}")
    
    return {"message": "Password reset instructions have been sent to your email"}

@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(email: str = Body(...), token: str = Body(...), new_password: str = Body(...), session: Session = Depends(get_session)):
    """
    Reset a user's password using the provided reset token.
    """
    expected_token = password_reset_tokens.get(email)
    if not expected_token or expected_token != token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token"
        )
    
    db_user = get_user_by_email(session, email)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update password after hashing
    user_update = UserUpdate(password=hash_password(new_password))
    updated_user = update_user(session, db_user.id, user_update)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password"
        )
    del password_reset_tokens[email]
    
    return {"message": "Password updated successfully"}


# Configure Google OAuth Client
oauth = OAuth()
oauth.register(
    "google",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    authorize_url="https://accounts.google.com/o/oauth2/auth",
    access_token_url="https://oauth2.googleapis.com/token",
    client_kwargs={"scope": "openid email profile"},
)

@router.get("/google/login")
async def google_login(request: Request):
    """
    Redirects the user to the Google login page.
    """
    return await oauth.google.authorize_redirect(request, settings.GOOGLE_REDIRECT_URI)

@router.get("/google/callback", response_model=Token)
async def google_callback(request: Request, session: Session = Depends(get_session)):
    """
    Handles Google OAuth callback: authenticates the user, creates an account if necessary, and returns a JWT token.
    """
    token = await oauth.google.authorize_access_token(request)
    user_info = await oauth.google.parse_id_token(request, token)
    
    if not user_info or "email" not in user_info:
        raise HTTPException(status_code=400, detail="Google authentication failed")
    
    email = user_info["email"]
    user = get_user_by_email(session, email)
    
    if not user:
        # Create a new user for OAuth login; mark as verified
        user_data = {
            "email": email,
            "name": user_info.get("name", ""),
            "is_verified": True,  # OAuth users are considered verified

