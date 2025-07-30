#!/usr/bin/env python3
"""
Test script to verify admin user creation functionality
"""

import asyncio
import os
from dotenv import load_dotenv
from app.db.database import AsyncSessionLocal
from app.crud.user import get_user_by_email
from app.scripts.auto_create_admin import create_admin_if_not_exists

# Load environment variables
load_dotenv()

async def test_admin_creation():
    """Test the admin creation functionality"""
    print("Testing admin user creation...")
    
    # Check environment variables
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    
    print(f"Admin Email from env: {admin_email}")
    print(f"Admin Password from env: {'*' * len(admin_password) if admin_password else 'None'}")
    
    if not admin_email or not admin_password:
        print("❌ Admin credentials not found in environment variables!")
        return False
    
    # Check if admin already exists before creation
    async with AsyncSessionLocal() as session:
        existing_admin = await get_user_by_email(session, admin_email)
        if existing_admin:
            print(f"✅ Admin user already exists: {existing_admin.email} (Admin: {existing_admin.is_admin})")
        else:
            print("ℹ️  No existing admin user found")
    
    # Run the admin creation function
    try:
        await create_admin_if_not_exists()
        print("✅ Admin creation function executed successfully")
    except Exception as e:
        print(f"❌ Error during admin creation: {str(e)}")
        return False
    
    # Verify admin was created/updated
    async with AsyncSessionLocal() as session:
        admin_user = await get_user_by_email(session, admin_email)
        if admin_user:
            print(f"✅ Admin user found: {admin_user.email}")
            print(f"   - Is Admin: {admin_user.is_admin}")
            print(f"   - Is Active: {admin_user.is_active}")
            print(f"   - Is Verified: {admin_user.is_verified}")
            print(f"   - Full Name: {admin_user.full_name}")
            
            if admin_user.is_admin and admin_user.is_active and admin_user.is_verified:
                print("✅ Admin user is properly configured!")
                return True
            else:
                print("❌ Admin user exists but is not properly configured")
                return False
        else:
            print("❌ Admin user was not created")
            return False

async def test_admin_login():
    """Test admin login functionality"""
    print("\nTesting admin login...")
    
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    
    # Import required modules for login test
    from app.crud.user import get_user_by_email
    from app.core.security import verify_password
    
    async with AsyncSessionLocal() as session:
        admin_user = await get_user_by_email(session, admin_email)
        if admin_user:
            # Test password verification
            password_valid = verify_password(admin_password, admin_user.hashed_password)
            if password_valid:
                print("✅ Admin password verification successful")
                return True
            else:
                print("❌ Admin password verification failed")
                return False
        else:
            print("❌ Admin user not found for login test")
            return False

async def main():
    """Main test function"""
    print("=" * 50)
    print("ADMIN USER CREATION TEST")
    print("=" * 50)
    
    # Test admin creation
    creation_success = await test_admin_creation()
    
    # Test admin login if creation was successful
    if creation_success:
        login_success = await test_admin_login()
        
        if login_success:
            print("\n🎉 All tests passed! Admin user is ready to use.")
        else:
            print("\n⚠️  Admin user created but login test failed.")
    else:
        print("\n❌ Admin creation failed.")
    
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(main())