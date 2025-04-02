"""
Database configuration with async support
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as AsyncSessionSQLModel

from app.core.config import settings

# Async engine for PostgreSQL
async_engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql:"),
    echo=True,  # Set to False in production
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
        # Create all tables
        await conn.run_sync(SQLModel.metadata.create_all)
        # Optional: Seed initial data
        # await seed_initial_data(conn)

async def get_db() -> AsyncSession:
    """
    Async database session dependency
    Usage:
    async def some_endpoint(db: AsyncSession = Depends(get_db)):
        ...
    """
    async with AsyncSessionLocal() as session:
        yield session

