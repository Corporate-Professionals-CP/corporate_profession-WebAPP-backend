from sqlmodel import SQLModel, create_engine, Session
from app.core.config import settings

# Create the SQLAlchemy engine for PostgreSQL.
engine = create_engine(
    settings.DATABASE_URL,
    echo=True  # Set to False in production for less verbose logging
)

def create_db_and_tables() -> None:
    """Create all database tables from SQLModel metadata."""
    SQLModel.metadata.create_all(engine)

def get_session():
    """Dependency generator for database sessions."""
    with Session(engine) as session:
        yield session

