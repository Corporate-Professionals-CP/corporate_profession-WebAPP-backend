import asyncio
import os
from app.db.database import AsyncSessionLocal
from app.models.user import User
from app.crud.user import get_user_by_email, create_user
from app.schemas.user import UserCreate
from pydantic import SecretStr
from app.core.config import settings

async def create_admin_if_not_exists():
    """Create an admin user if it doesn't already exist"""
    # Get admin credentials from environment variables
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    
    if not admin_email or not admin_password:
        print("Admin credentials not found in environment variables. Skipping admin creation.")
        return
    
    async with AsyncSessionLocal() as session:
        # Check if admin already exists
        existing_admin = await get_user_by_email(session, admin_email)
        
        if existing_admin:
            # If user exists but is not admin, make them admin
            if not existing_admin.is_admin:
                existing_admin.is_admin = True
                existing_admin.is_verified = True
                existing_admin.is_active = True
                session.add(existing_admin)
                await session.commit()
                print(f"User {admin_email} has been upgraded to admin.")
            else:
                print(f"Admin {admin_email} already exists.")
        else:
            # Create new admin user
            user_data = UserCreate(
                full_name="System Administrator",
                email=admin_email,
                password=SecretStr(admin_password),
                password_confirmation=SecretStr(admin_password)
            )
            
            try:
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
                print(f"Error creating admin user: {str(e)}")
                await session.rollback()

if __name__ == "__main__":
    # This allows the script to be run directly for testing
    asyncio.run(create_admin_if_not_exists())