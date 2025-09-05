import asyncio
import os
from dotenv import load_dotenv
from app.db.database import AsyncSessionLocal

# Load environment variables from .env file
load_dotenv()
from app.models.user import User
from app.crud.user import get_user_by_email, create_user
from app.schemas.user import UserCreate
from pydantic import SecretStr
from app.core.config import settings

async def create_admin_if_not_exists():
    """Create an admin user if it doesn't already exist, or fix existing user"""
    # Get admin credentials from environment variables
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    
    if not admin_email or not admin_password:
        print("Admin credentials not found in environment variables. Skipping admin creation.")
        return
    
    async with AsyncSessionLocal() as session:
        try:
            # Check if admin already exists
            existing_admin = await get_user_by_email(session, admin_email)
            
            if existing_admin:
                print(f"User {admin_email} found. Checking admin status...")
                
                # Import password verification functions
                from app.core.security import verify_password, get_password_hash
                
                # Check and fix admin privileges
                needs_update = False
                
                if not existing_admin.is_admin:
                    print("  - Setting is_admin = True")
                    existing_admin.is_admin = True
                    needs_update = True
                
                if not existing_admin.is_verified:
                    print("  - Setting is_verified = True")
                    existing_admin.is_verified = True
                    needs_update = True
                
                if not existing_admin.is_active:
                    print("  - Setting is_active = True")
                    existing_admin.is_active = True
                    needs_update = True
                
                # Check and fix password if needed
                if not verify_password(admin_password, existing_admin.hashed_password):
                    print("  - Updating password hash")
                    existing_admin.hashed_password = get_password_hash(admin_password)
                    needs_update = True
                
                if needs_update:
                    session.add(existing_admin)
                    await session.commit()
                    print(f"Admin user {admin_email} has been updated with correct privileges.")
                else:
                    print(f"Admin {admin_email} already exists with correct configuration.")
            else:
                # Create new admin user
                print(f"Creating new admin user: {admin_email}")
                user_data = UserCreate(
                    full_name="System Administrator",
                    email=admin_email,
                    password=SecretStr(admin_password),
                    password_confirmation=SecretStr(admin_password)
                )
                
                # Create the user
                new_admin = await create_user(session, user_data)
                
                # Set admin privileges
                new_admin.is_admin = True
                new_admin.is_verified = True
                new_admin.is_active = True
                
                session.add(new_admin)
                await session.commit()
                print(f"Admin user {admin_email} created successfully.")
                
        except Exception as e:
            print(f"Error handling admin user: {str(e)}")
            await session.rollback()
            raise

if __name__ == "__main__":
    # This allows the script to be run directly for testing
    asyncio.run(create_admin_if_not_exists())