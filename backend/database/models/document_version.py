from enum import Enum
from typing import Optional
import uuid
from sqlalchemy import Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import  UUID
from sqlalchemy.orm import Mapped, mapped_column
from database.models.base_model import AuditMixin, Base

class MediaType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MD = "md"
    PNG = "png"
    HTML = "html"
    CSV = "csv"

class DocumentVersion(Base, AuditMixin):
    __tablename__ = "document_versions"

    versionId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    documentId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    mediaType: Mapped[MediaType] = mapped_column(SAEnum(MediaType, name="media_type"), nullable=False)
    workspaceId: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True
    )
    hash: Mapped[str] = mapped_column(String(128), nullable=False)