import pytest
from httpx import AsyncClient
from uuid import uuid4
from app.main import app
from app.models.user import User
from app.core.security import create_access_token

@pytest.mark.asyncio
async def test_list_moderators(client: AsyncClient, test_db, admin_user):
    # Create admin token
    admin_token = create_access_token(str(admin_user.id), scopes=["admin"])
    
    # Test listing moderators
    response = await client.get(
        "/api/admin/moderators/",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    assert isinstance(response.json(), list)

@pytest.mark.asyncio
async def test_make_moderator(client: AsyncClient, test_db, admin_user, test_user):
    # Create admin token
    admin_token = create_access_token(str(admin_user.id), scopes=["admin"])
    
    # Make user a moderator
    response = await client.post(
        f"/api/admin/moderators/{test_user.id}/make",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(test_user.id)
    assert data["is_moderator"] == True
    
    # Verify in database
    user = await test_db.get(User, test_user.id)
    assert user.is_moderator == True

@pytest.mark.asyncio
async def test_remove_moderator(client: AsyncClient, test_db, admin_user, test_user):
    # First make the user a moderator
    test_user.is_moderator = True
    test_db.add(test_user)
    await test_db.commit()
    await test_db.refresh(test_user)
    
    # Create admin token
    admin_token = create_access_token(str(admin_user.id), scopes=["admin"])
    
    # Remove moderator status
    response = await client.delete(
        f"/api/admin/moderators/{test_user.id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(test_user.id)
    assert data["is_moderator"] == False
    
    # Verify in database
    user = await test_db.get(User, test_user.id)
    assert user.is_moderator == False

@pytest.mark.asyncio
async def test_non_admin_cannot_manage_moderators(client: AsyncClient, test_db, test_user):
    # Create regular user token
    user_token = create_access_token(str(test_user.id), scopes=["user"])
    
    # Try to list moderators
    response = await client.get(
        "/api/admin/moderators/",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    
    assert response.status_code == 403
    
    # Try to make a moderator
    response = await client.post(
        f"/api/admin/moderators/{test_user.id}/make",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    
    assert response.status_code == 403
    
    # Try to remove a moderator
    response = await client.delete(
        f"/api/admin/moderators/{test_user.id}",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    
    assert response.status_code == 403