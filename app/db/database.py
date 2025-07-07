"""
Database configuration with async support
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as AsyncSessionSQLModel
from typing import AsyncGenerator

from app.core.config import settings

# Configure logging based on environment
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Log environment information
logger.info(f"Environment: {getattr(settings, 'ENVIRONMENT', 'Unknown')}")
logger.info(f"Database URL configured: {bool(settings.DATABASE_URL)}")

# Use the original DATABASE_URL and modify for asyncpg
async_engine = create_async_engine(
    str(settings.DATABASE_URL).replace("postgresql://", "postgresql+asyncpg://", 1),
    echo=True,  # will be False in production
    future=True,  # Required for SQLModel async support
    pool_size=20,  # Number of connections to maintain
    max_overflow=30,  # Additional connections that can be created
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=3600,  # Recycle connections after 1 hour
    connect_args={
        "server_settings": {
            "application_name": "corporate_professionals_app",
        }
    }
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

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async database session dependency
    Usage:
    async def some_endpoint(db: AsyncSession = Depends(get_db)):
        ...
    """
    try:
        logger.info("Creating database session...")
        async with AsyncSessionLocal() as session:
            logger.info("Database session created successfully")
            yield session
    except Exception as e:
        logger.error(f"Database session creation failed: {str(e)}", exc_info=True)
        raise

@asynccontextmanager
async def get_db_with_retry(max_retries: int = 3):
    """
    Database session with retry logic for connection issues
    """
    for attempt in range(max_retries):
        try:
            async with AsyncSessionLocal() as session:
                yield session
                return
        except Exception as e:
            logger.warning(f"Database connection attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(1)  # Wait before retry
