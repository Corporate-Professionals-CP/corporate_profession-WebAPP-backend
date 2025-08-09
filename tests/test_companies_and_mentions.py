import pytest
import pytest_asyncio
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.db.database import get_db
from app.models.user import User
from app.models.company import Company, CompanyAdmin, CompanyFollower
from app.models.post import Post
from app.models.post_mention import PostMention
from app.core.security import create_access_token
from datetime import datetime, timedelta
import uuid


@pytest_asyncio.fixture
async def client(async_test_session: AsyncSession):
    """Create test client with database session override"""
    def override_get_db():
        return async_test_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    from httpx import ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    
    # Clean up
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def db_session(async_test_session: AsyncSession):
    """Provide database session for tests"""
    return async_test_session


class TestCompanies:
    """Test suite for company functionality"""
    
    @pytest_asyncio.fixture
    async def test_user(self, db_session: AsyncSession):
        """Create a test user"""
        user = User(
            id=str(uuid.uuid4()),
            full_name="Test User",
            email="testuser@example.com",
            username="testuser",
            first_name="Test",
            last_name="User",
            hashed_password="hashed_password",
            is_active=True,
            is_verified=True
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user
    
    @pytest_asyncio.fixture
    async def auth_headers(self, test_user: User):
        """Create authentication headers for test user"""
        access_token = create_access_token(
            user_id=test_user.id,
            expires_delta=timedelta(minutes=30)
        )
        return {"Authorization": f"Bearer {access_token}"}
    
    @pytest_asyncio.fixture
    async def test_company(self, db_session: AsyncSession, test_user: User):
        """Create a test company"""
        company = Company(
            id=str(uuid.uuid4()),
            name="Test Company",
            username="testcompany",
            description="A test company for testing purposes",
            industry="Technology",
            company_type="startup",
            website="https://testcompany.com",
            visibility="PUBLIC"
        )
        db_session.add(company)
        await db_session.commit()
        await db_session.refresh(company)
        
        # Add test user as admin
        admin = CompanyAdmin(
            id=str(uuid.uuid4()),
            company_id=company.id,
            user_id=test_user.id,
            role="admin"
        )
        db_session.add(admin)
        await db_session.commit()
        
        return company
    
    @pytest.mark.asyncio
    async def test_create_company(self, client: AsyncClient, auth_headers: dict):
        """Test creating a new company"""
        company_data = {
            "name": "New Test Company",
            "username": "newtestcompany",
            "description": "A new test company",
            "industry": "Finance",
            "company_type": "corporation",
            "website": "https://newtestcompany.com"
        }
        
        response = await client.post(
            "/api/companies/",
            json=company_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == company_data["name"]
        assert data["username"] == company_data["username"]
        assert data["industry"] == company_data["industry"]
        assert data["company_type"] == company_data["company_type"]
    
    @pytest.mark.asyncio
    async def test_get_company_by_username(self, client: AsyncClient, test_company: Company):
        """Test retrieving a company by username"""
        response = await client.get(f"/api/companies/username/{test_company.username}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == test_company.username
        assert data["name"] == test_company.name
    
    @pytest.mark.asyncio
    async def test_follow_company(self, client: AsyncClient, auth_headers: dict, test_company: Company):
        """Test following a company"""
        response = await client.post(
            f"/api/companies/{test_company.id}/follow",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Successfully followed company"
    
    @pytest.mark.asyncio
    async def test_unfollow_company(self, client: AsyncClient, auth_headers: dict, test_company: Company, db_session: AsyncSession, test_user: User):
        """Test unfollowing a company"""
        # First follow the company
        follower = CompanyFollower(
            id=str(uuid.uuid4()),
            company_id=test_company.id,
            user_id=test_user.id
        )
        db_session.add(follower)
        await db_session.commit()
        
        # Then unfollow
        response = await client.delete(
            f"/api/companies/{test_company.id}/follow",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Successfully unfollowed company"
    
    @pytest.mark.asyncio
    async def test_search_companies(self, client: AsyncClient, test_company: Company):
        """Test searching for companies"""
        response = await client.get(
            "/api/companies/search",
            params={"query": "Test"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert any(company["name"] == test_company.name for company in data)


class TestMentions:
    """Test suite for user mention functionality"""
    
    @pytest_asyncio.fixture
    async def test_users(self, db_session: AsyncSession):
        """Create multiple test users"""
        users = []
        # Use timestamp to make usernames/emails unique
        import time
        timestamp = str(int(time.time() * 1000))  # milliseconds
        
        for i in range(3):
            user = User(
                id=str(uuid.uuid4()),
                email=f"testuser{i}_{timestamp}@example.com",
                username=f"testuser{i}_{timestamp}",
                first_name=f"TestUser{i}",
                last_name="Mention",
                hashed_password="hashed_password",
                is_active=True,
                is_verified=True
            )
            db_session.add(user)
            users.append(user)
        
        await db_session.commit()
        for user in users:
            await db_session.refresh(user)
        return users
    
    @pytest_asyncio.fixture
    async def auth_headers_user0(self, test_users: list):
        """Create authentication headers for first test user"""
        access_token = create_access_token(
            user_id=test_users[0].id,
            expires_delta=timedelta(minutes=30)
        )
        return {"Authorization": f"Bearer {access_token}"}
    
    @pytest_asyncio.fixture
    async def test_post_with_mentions(self, db_session: AsyncSession, test_users: list):
        """Create a test post with mentions"""
        post = Post(
            id=str(uuid.uuid4()),
            content="Hello @user1 and @user2, how are you?",
            author_id=test_users[0].id
        )
        db_session.add(post)
        await db_session.commit()
        await db_session.refresh(post)
        
        # Add mentions
        mentions = [
            PostMention(
                id=str(uuid.uuid4()),
                post_id=post.id,
                mentioned_user_id=test_users[1].id,
                mentioned_by_user_id=test_users[0].id,
                mention_text="@user1",
                position_start=6,
                position_end=12
            ),
            PostMention(
                id=str(uuid.uuid4()),
                post_id=post.id,
                mentioned_user_id=test_users[2].id,
                mentioned_by_user_id=test_users[0].id,
                mention_text="@user2",
                position_start=17,
                position_end=23
            )
        ]
        
        for mention in mentions:
            db_session.add(mention)
        await db_session.commit()
        
        return post
    
    @pytest.mark.asyncio
    async def test_search_users_for_mentions(self, client: AsyncClient, auth_headers_user0: dict, test_users: list):
        """Test searching users for mentions autocomplete"""
        response = await client.get(
            "/api/mentions/search",
            params={"query": "user"},
            headers=auth_headers_user0
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2  # Should find user1 and user2
        usernames = [user["username"] for user in data]
        assert "user1" in usernames
        assert "user2" in usernames
    
    @pytest.mark.asyncio
    async def test_get_mentions_for_post(self, client: AsyncClient, test_post_with_mentions: Post, test_users: list):
        """Test retrieving mentions for a specific post"""
        response = await client.get(f"/api/mentions/post/{test_post_with_mentions.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        
        # Check mention details
        mention_texts = [mention["mention_text"] for mention in data]
        assert "@user1" in mention_texts
        assert "@user2" in mention_texts
    
    @pytest.mark.asyncio
    async def test_get_my_mentions(self, client: AsyncClient, test_users: list, test_post_with_mentions: Post):
        """Test retrieving mentions where current user was mentioned"""
        # Create auth headers for user1 (who was mentioned)
        access_token = create_access_token(
            user_id=test_users[1].id,
            expires_delta=timedelta(minutes=30)
        )
        auth_headers = {"Authorization": f"Bearer {access_token}"}
        
        response = await client.get(
            "/api/mentions/my-mentions",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        
        # Check that user1 was mentioned in the post
        mention = data[0]
        assert mention["post_id"] == test_post_with_mentions.id
        assert mention["mention_text"] == "@user1"
    
    @pytest.mark.asyncio
    async def test_get_user_mention_info(self, client: AsyncClient, test_users: list):
        """Test retrieving user information for mention display"""
        response = await client.get(f"/api/mentions/user/{test_users[1].id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_users[1].id
        assert data["username"] == test_users[1].username
        assert data["first_name"] == test_users[1].first_name
        assert data["last_name"] == test_users[1].last_name


class TestCompanyPosts:
    """Test suite for company posts functionality"""
    
    @pytest_asyncio.fixture
    async def test_setup(self, db_session: AsyncSession):
        """Create test user and company"""
        user = User(
            id=str(uuid.uuid4()),
            email="companyuser@example.com",
            username="companyuser",
            first_name="Company",
            last_name="User",
            hashed_password="hashed_password",
            is_active=True,
            is_verified=True
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        company = Company(
            id=str(uuid.uuid4()),
            name="Post Test Company",
            username="posttestcompany",
            description="A company for testing posts",
            industry="Technology",
            company_type="startup",
            visibility="PUBLIC"
        )
        db_session.add(company)
        await db_session.commit()
        await db_session.refresh(company)
        
        # Add user as company admin
        admin = CompanyAdmin(
            id=str(uuid.uuid4()),
            company_id=company.id,
            user_id=user.id,
            role="admin"
        )
        db_session.add(admin)
        await db_session.commit()
        
        return user, company
    
    @pytest.mark.asyncio
    async def test_create_company_post(self, client: AsyncClient, test_setup):
        """Test creating a post on behalf of a company"""
        user, company = test_setup
        
        access_token = create_access_token(
            user_id=user.id,
            expires_delta=timedelta(minutes=30)
        )
        auth_headers = {"Authorization": f"Bearer {access_token}"}
        
        post_data = {
            "content": "This is a company post from our official account!",
            "company_id": company.id
        }
        
        response = await client.post(
            "/api/posts/",
            json=post_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["content"] == post_data["content"]
        assert data["company_id"] == company.id
        assert data["author_id"] == user.id


class TestIntegration:
    """Integration tests combining companies and mentions"""
    
    @pytest.mark.asyncio
    async def test_company_post_with_mentions(self, client: AsyncClient, db_session: AsyncSession):
        """Test creating a company post that mentions users"""
        # Create test users
        users = []
        for i in range(2):
            user = User(
                id=str(uuid.uuid4()),
                email=f"integrationuser{i}@example.com",
                username=f"integrationuser{i}",
                first_name=f"Integration{i}",
                last_name="User",
                hashed_password="hashed_password",
                is_active=True,
                is_verified=True
            )
            db_session.add(user)
            users.append(user)
        
        await db_session.commit()
        for user in users:
            await db_session.refresh(user)
        
        # Create company
        company = Company(
            id=str(uuid.uuid4()),
            name="Integration Test Company",
            username="integrationtestcompany",
            description="A company for integration testing",
            industry="Technology",
            company_type="startup",
            visibility="PUBLIC"
        )
        db_session.add(company)
        await db_session.commit()
        await db_session.refresh(company)
        
        # Add first user as company admin
        admin = CompanyAdmin(
            id=str(uuid.uuid4()),
            company_id=company.id,
            user_id=users[0].id,
            role="admin"
        )
        db_session.add(admin)
        await db_session.commit()
        
        # Create auth headers
        access_token = create_access_token(
            user_id=users[0].id,
            expires_delta=timedelta(minutes=30)
        )
        auth_headers = {"Authorization": f"Bearer {access_token}"}
        
        # Create company post with mention
        post_data = {
            "content": f"Welcome to our team @{users[1].username}! We're excited to have you.",
            "company_id": company.id
        }
        
        response = await client.post(
            "/api/posts/",
            json=post_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["content"] == post_data["content"]
        assert data["company_id"] == company.id
        
        # Verify the post was created successfully
        post_id = data["id"]
        
        # Test that we can retrieve the company that made the post
        company_response = await client.get(f"/api/companies/username/{company.username}")
        assert company_response.status_code == 200
        company_data = company_response.json()
        assert company_data["name"] == company.name