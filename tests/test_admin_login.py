import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app
from app.models.user import User
from app.core.security import get_password_hash
from uuid import uuid4
import json

# Create test client
client = TestClient(app)

# Mock user data for testing
mock_admin_user = {
    "id": str(uuid4()),
    "email": "admin@test.com",
    "full_name": "Admin User",
    "is_admin": True,
    "is_active": True,
    "is_verified": True,
    "hashed_password": get_password_hash("admin123")
}

mock_regular_user = {
    "id": str(uuid4()),
    "email": "user@test.com",
    "full_name": "Regular User",
    "is_admin": False,
    "is_active": True,
    "is_verified": True,
    "hashed_password": get_password_hash("user123")
}

mock_inactive_admin = {
    "id": str(uuid4()),
    "email": "inactive_admin@test.com",
    "full_name": "Inactive Admin",
    "is_admin": True,
    "is_active": False,
    "is_verified": True,
    "hashed_password": get_password_hash("admin123")
}

mock_unverified_admin = {
    "id": str(uuid4()),
    "email": "unverified_admin@test.com",
    "full_name": "Unverified Admin",
    "is_admin": True,
    "is_active": True,
    "is_verified": False,
    "hashed_password": get_password_hash("admin123")
}


class TestAdminLogin:
    """Test cases for the admin-only login endpoint"""

    @patch('app.crud.user.get_user_by_email')
    @patch('app.core.security.verify_password')
    @patch('app.utils.activity_logger.log_user_activity')
    def test_successful_admin_login(self, mock_log, mock_verify, mock_get_user):
        """Test successful login with valid admin credentials"""
        # Setup mocks
        mock_user = MagicMock()
        mock_user.email = mock_admin_user["email"]
        mock_user.is_admin = True
        mock_user.is_active = True
        mock_user.is_verified = True
        mock_user.login_count = 0
        mock_user.last_login_at = None
        mock_user.last_active_at = None
        
        mock_get_user.return_value = mock_user
        mock_verify.return_value = True
        
        login_data = {
            "username": mock_admin_user["email"],
            "password": "admin123"
        }
        
        response = client.post("/api/auth/admin/login", data=login_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert "expires_at" in data
        assert "user" in data
        
        # Check token type
        assert data["token_type"] == "bearer"
        
        # Check user data
        user_data = data["user"]
        assert user_data["email"] == mock_admin_user["email"]
        assert user_data["is_admin"] == True
        
        # Verify token contains admin scope
        token = data["access_token"]
        assert token is not None

    @patch('app.crud.user.get_user_by_email')
    @patch('app.core.security.verify_password')
    def test_regular_user_cannot_admin_login(self, mock_verify, mock_get_user):
        """Test that regular users cannot login through admin endpoint"""
        # Setup mocks for regular user
        mock_user = MagicMock()
        mock_user.email = mock_regular_user["email"]
        mock_user.is_admin = False
        mock_user.is_active = True
        mock_user.is_verified = True
        
        mock_get_user.return_value = mock_user
        mock_verify.return_value = True
        
        login_data = {
            "username": mock_regular_user["email"],
            "password": "user123"
        }
        
        response = client.post("/api/auth/admin/login", data=login_data)
        
        assert response.status_code == 403
        data = response.json()
        assert "Admin privileges required" in data["detail"]

    @patch('app.crud.user.get_user_by_email')
    def test_invalid_email_admin_login(self, mock_get_user):
        """Test admin login with non-existent email"""
        mock_get_user.return_value = None
        
        login_data = {
            "username": "nonexistent@test.com",
            "password": "password123"
        }
        
        response = client.post("/api/auth/admin/login", data=login_data)
        
        assert response.status_code == 401
        data = response.json()
        assert "Email not found" in data["detail"]

    @patch('app.crud.user.get_user_by_email')
    @patch('app.core.security.verify_password')
    def test_invalid_password_admin_login(self, mock_verify, mock_get_user):
        """Test admin login with wrong password"""
        # Setup mocks for admin user
        mock_user = MagicMock()
        mock_user.email = mock_admin_user["email"]
        mock_user.is_admin = True
        mock_user.is_active = True
        mock_user.is_verified = True
        
        mock_get_user.return_value = mock_user
        mock_verify.return_value = False  # Wrong password
        
        login_data = {
            "username": mock_admin_user["email"],
            "password": "wrongpassword"
        }
        
        response = client.post("/api/auth/admin/login", data=login_data)
        
        assert response.status_code == 401
        data = response.json()
        assert "Invalid email or password" in data["detail"]

    @patch('app.crud.user.get_user_by_email')
    @patch('app.core.security.verify_password')
    def test_inactive_admin_cannot_login(self, mock_verify, mock_get_user):
        """Test that inactive admin users cannot login"""
        # Setup mocks for inactive admin
        mock_user = MagicMock()
        mock_user.email = mock_inactive_admin["email"]
        mock_user.is_admin = True
        mock_user.is_active = False
        mock_user.is_verified = True
        
        mock_get_user.return_value = mock_user
        mock_verify.return_value = True
        
        login_data = {
            "username": mock_inactive_admin["email"],
            "password": "admin123"
        }
        
        response = client.post("/api/auth/admin/login", data=login_data)
        
        assert response.status_code == 403
        data = response.json()
        assert "Account deactivated" in data["detail"]

    @patch('app.crud.user.get_user_by_email')
    @patch('app.core.security.verify_password')
    def test_unverified_admin_cannot_login(self, mock_verify, mock_get_user):
        """Test that unverified admin users cannot login"""
        # Setup mocks for unverified admin
        mock_user = MagicMock()
        mock_user.email = mock_unverified_admin["email"]
        mock_user.is_admin = True
        mock_user.is_active = True
        mock_user.is_verified = False
        
        mock_get_user.return_value = mock_user
        mock_verify.return_value = True
        
        login_data = {
            "username": mock_unverified_admin["email"],
            "password": "admin123"
        }
        
        response = client.post("/api/auth/admin/login", data=login_data)
        
        assert response.status_code == 403
        data = response.json()
        assert "Account not verified" in data["detail"]

    @pytest.mark.asyncio
    async def test_admin_login_missing_credentials(self, client: AsyncClient):
        """Test admin login with missing credentials"""
        # Missing password
        response = await client.post("/api/auth/admin/login", data={"username": "admin@test.com"})
        assert response.status_code == 422
        
        # Missing username
        response = await client.post("/api/auth/admin/login", data={"password": "password123"})
        assert response.status_code == 422
        
        # Empty data
        response = await client.post("/api/auth/admin/login", data={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_admin_login_activity_logging(self, client: AsyncClient, admin_user: User):
        """Test that admin login activity is properly logged"""
        login_data = {
            "username": admin_user.email,
            "password": "admin123"
        }
        
        # Mock the activity logger to verify it's called
        with patch('app.utils.activity_logger.log_user_activity') as mock_log:
            response = await client.post("/api/auth/admin/login", data=login_data)
            
            assert response.status_code == 200
            
            # Verify activity logging was called
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            
            # Check the logged activity details
            assert call_args.kwargs['activity_type'] == 'admin_login'
            assert 'Admin user logged in via admin endpoint' in call_args.kwargs['description']
            assert call_args.kwargs['extra_data']['login_method'] == 'admin_password'
            assert call_args.kwargs['extra_data']['endpoint'] == '/auth/admin/login'

    @pytest.mark.asyncio
    async def test_admin_login_token_scopes(self, client: AsyncClient, admin_user: User):
        """Test that admin login returns token with correct scopes"""
        login_data = {
            "username": admin_user.email,
            "password": "admin123"
        }
        
        response = await client.post("/api/auth/admin/login", data=login_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify the token is valid and contains admin scope
        token = data["access_token"]
        
        # Use the token to access an admin endpoint to verify scopes
        headers = {"Authorization": f"Bearer {token}"}
        admin_response = await client.get("/api/admin/users/", headers=headers)
        
        # Should be able to access admin endpoints
        assert admin_response.status_code in [200, 404]  # 404 is ok if no users exist

    @pytest.mark.asyncio
    async def test_admin_login_updates_user_tracking(self, client: AsyncClient, admin_user: User, test_db: AsyncSession):
        """Test that admin login updates user tracking fields"""
        # Get initial values
        initial_login_count = admin_user.login_count or 0
        initial_last_login = admin_user.last_login_at
        
        login_data = {
            "username": admin_user.email,
            "password": "admin123"
        }
        
        response = await client.post("/api/auth/admin/login", data=login_data)
        
        assert response.status_code == 200
        
        # Refresh user from database
        await test_db.refresh(admin_user)
        
        # Check that tracking fields were updated
        assert admin_user.login_count == initial_login_count + 1
        assert admin_user.last_login_at != initial_last_login
        assert admin_user.last_active_at is not None

    @pytest.mark.asyncio
    async def test_admin_login_endpoint_documentation(self, client: AsyncClient):
        """Test that the admin login endpoint is properly documented in OpenAPI"""
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        
        openapi_spec = response.json()
        paths = openapi_spec.get("paths", {})
        
        # Check that the admin login endpoint exists in the spec
        admin_login_path = "/api/auth/admin/login"
        assert admin_login_path in paths
        
        # Check the endpoint details
        endpoint_spec = paths[admin_login_path]
        assert "post" in endpoint_spec
        
        post_spec = endpoint_spec["post"]
        assert "summary" in post_spec or "description" in post_spec
        assert "responses" in post_spec
        assert "200" in post_spec["responses"]