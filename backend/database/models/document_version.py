from enum import Enum
from typing import Optional
import uuid
from sqlalchemy import Enum as SAEnum, ForeignKey, BigInteger, String, Text
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

class DocumentVersionStatus(str, Enum):
    PENDING = "pending"
    AVAILABLE = "available"
    ABORTED = "aborted"

class DocumentVersion(Base, AuditMixin):
    __tablename__ = "document_versions"

    versionId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    documentId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[DocumentVersionStatus] = mapped_column(
        SAEnum(DocumentVersionStatus, name="document_version_status", values_callable=lambda e: [m.value for m in e]),
        default=DocumentVersionStatus.PENDING,
        nullable=False,
    )
    objectKey: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    uploadId: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fileSize: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    mediaType: Mapped[MediaType] = mapped_column(
        SAEnum(MediaType, name="media_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    workspaceId: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True
    )
    hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
