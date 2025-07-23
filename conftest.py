import pytest
import pytest_asyncio
import asyncio
import greenlet
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as AsyncSessionSQLModel
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Register the asyncio marker
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "asyncio: mark test as an asyncio coroutine"
    )

# Configure pytest-asyncio to use auto mode instead of strict
# This helps prevent issues with greenlet context
pytest_plugins = ["pytest_asyncio"]
pytest_asyncio_mode = "auto"

@pytest.fixture(scope="function")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="function")
async def async_test_engine():
    """Create a test async engine for each test."""
    # Use test database URL if available, otherwise use the main database URL
    db_url = settings.TEST_DATABASE_URL or settings.DATABASE_URL
    
    # Create async engine with modified URL for asyncpg
    test_engine = create_async_engine(
        str(db_url).replace("postgresql://", "postgresql+asyncpg://", 1),
        echo=False,
        future=True,
        pool_pre_ping=True,
        # Configure connection pool for testing
        poolclass=None  # Use NullPool for tests to avoid connection issues
    )
    
    yield test_engine
    await test_engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def async_test_session(async_test_engine):
    """Create a test async session for each test."""
    # Create session factory
    TestSessionLocal = sessionmaker(
        bind=async_test_engine,
        class_=AsyncSessionSQLModel,
        expire_on_commit=False,
        autoflush=False
    )
    
    # Create session
    async with TestSessionLocal() as session:
        # Start a transaction
        await session.begin()
        try:
            yield session
        finally:
            # Roll back the transaction after the test is complete
            await session.rollback()
            await session.close()