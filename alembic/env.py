import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Import SQLModel and all models that should be included in migrations
from sqlmodel import SQLModel
from app.models.user import User

# Import all other models to ensure they're registered with SQLModel
import app.models

# Import settings for database configuration
from app.core.config import settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set SQLModel metadata as target for migrations
target_metadata = SQLModel.metadata

# Get the database URL from settings
db_url = str(settings.DATABASE_URL).replace("postgresql://", "postgresql+asyncpg://", 1)

# We don't set the URL in the config directly to avoid interpolation issues
# Instead, we'll use it directly in the configuration functions

# Define a function to filter out DROP statements for existing tables and indexes
def include_object(obj, name, type_, reflected, compare_to):
    # We want to completely prevent any DROP operations in migrations
    # This is critical for production databases where we can't lose data
    
    # First, check if this is a DROP operation
    if obj is None and compare_to is not None:
        # This is a DROP operation, always prevent it
        return False
    
    # If this is a table or index that exists in the models but not in the DB,
    # we want to create it (this is a new table/index)
    if not reflected and compare_to is None and obj is not None:
        # This is a CREATE operation for a new object
        return True
        
    # If this is a table or index that exists in both models and DB,
    # we want to allow modifications (ALTER) but not drops
    if reflected and compare_to is not None and obj is not None:
        # This is an ALTER operation for an existing object
        return True
    
    # For any other case, prevent the operation to be safe
    # This includes DROP operations for tables not in the models
    return False


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Create a config section with our database URL
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = db_url
    
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
