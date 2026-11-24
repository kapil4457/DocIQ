from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from database.models.base_model import Base
from config import get_database_url

from database.models import (  # noqa: F401
     document, document_embedding, document_version, organization, user, workspace
)
engine = create_engine(get_database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE document_versions ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(64)"
        ))
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_document_versions_idempotency_key "
            "ON document_versions (idempotency_key)"
        ))
        for status_value in ("uploaded", "processing", "ingesting"):
            conn.execute(text(
                "ALTER TYPE document_version_status ADD VALUE IF NOT EXISTS :value"
            ), {"value": status_value})

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
