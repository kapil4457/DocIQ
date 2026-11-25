"""Database engine and session management for Document Service."""

from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from document_service.config import get_settings

settings = get_settings()

# Create engine with connection pooling
engine = create_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def init_db() -> None:
    """Initialize database - create extensions and verify connection."""
    with engine.begin() as conn:
        # Enable pgvector extension
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    print("Database initialized successfully")
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE document_versions ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0 NOT NULL"
        ))


def get_db() -> Generator[Session, None, None]:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_sync() -> Session:
    """Get a synchronous database session (for background tasks)."""
    return SessionLocal()