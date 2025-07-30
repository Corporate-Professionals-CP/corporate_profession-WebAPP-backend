#!/usr/bin/env python3
"""
Test script to verify admin login endpoint functionality
"""

import asyncio
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_admin_login_endpoint():
    """Test the admin login endpoint"""
    print("Testing admin login endpoint...")
    
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    
    if not admin_email or not admin_password:
        print("❌ Admin credentials not found in environment variables!")
        return False
    
    # Test data
    login_data = {
        "username": admin_email,
        "password": admin_password
    }
    
    try:
        # Test admin login endpoint
        print(f"Testing login for: {admin_email}")
        response = requests.post(
            "http://localhost:8000/api/auth/admin/login",
            data=login_data,
            timeout=10
        )
        
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Admin login successful!")
            print(f"   - Access token received: {bool(data.get('access_token'))}")
            print(f"   - Token type: {data.get('token_type')}")
            print(f"   - User is admin: {data.get('user', {}).get('is_admin')}")
            print(f"   - User email: {data.get('user', {}).get('email')}")
            return True
        else:
            print(f"❌ Admin login failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data.get('detail', 'Unknown error')}")
            except:
                print(f"   Raw response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure the app is running on http://localhost:8000")
        return False
    except Exception as e:
        print(f"❌ Error testing admin login: {str(e)}")
        return False

def test_regular_login_endpoint():
    """Test the regular login endpoint for comparison"""
    print("\nTesting regular login endpoint...")
    
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    
    login_data = {
        "username": admin_email,
        "password": admin_password
    }
    
    try:
        response = requests.post(
            "http://localhost:8000/api/auth/token",
            data=login_data,
            timeout=10
        )
        
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Regular login successful!")
            print(f"   - Access token received: {bool(data.get('access_token'))}")
            print(f"   - User is admin: {data.get('user', {}).get('is_admin')}")
            return True
        else:
            print(f"❌ Regular login failed: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server")
        return False
    except Exception as e:
        print(f"❌ Error testing regular login: {str(e)}")
        return False

def main():
    """Main test function"""
    print("=" * 50)
    print("ADMIN LOGIN ENDPOINT TEST")
    print("=" * 50)
    
    # Test admin login endpoint
    admin_login_success = test_admin_login_endpoint()
    
    # Test regular login endpoint for comparison
    regular_login_success = test_regular_login_endpoint()
    
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    
    if admin_login_success and regular_login_success:
        print("🎉 All tests passed! Admin login is working correctly.")
    elif admin_login_success:
        print("✅ Admin login works, but regular login failed.")
    elif regular_login_success:
        print("⚠️  Regular login works, but admin login failed.")
    else:
        print("❌ Both login endpoints failed. Check if the server is running.")
    
    print("\nTo start the server, run: uvicorn app.main:app --reload")

if __name__ == "__main__":
    main()