from typing import Any
import uuid
from pgvector.sqlalchemy import Vector
from sqlalchemy import  ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from database.models.base_model import Base


class DocumentEmbedding(Base):
    __tablename__ = "document_embeddings"

    documentEmbeddingId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    documentId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False)
