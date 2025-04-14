"""
Database configuration with async support
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as AsyncSessionSQLModel

from app.core.config import settings

# Use the original DATABASE_URL and modify for asyncpg
async_engine = create_async_engine(
    str(settings.DATABASE_URL).replace("postgresql://", "postgresql+asyncpg://", 1),
    echo=True,  # will be False in production
    future=True  # Required for SQLModel async support
)

# Async session factory
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSessionSQLModel,
    expire_on_commit=False,
    autoflush=False
)

async def init_db():
    """Initialize database tables"""
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

async def get_db() -> AsyncSession:
    """
    Async database session dependency
    Usage:
    async def some_endpoint(db: AsyncSession = Depends(get_db)):
        ...
    """
    async with AsyncSessionLocal() as session:
        yield session
