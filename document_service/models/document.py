"""Document and DocumentVersion models."""

import uuid
from enum import Enum
from datetime import datetime
from sqlalchemy import Enum as SAEnum, ForeignKey, Text, String, BigInteger, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from document_service.models.base import Base, AuditMixin


class MediaType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MD = "md"
    PNG = "png"
    HTML = "html"
    CSV = "csv"
    XLSX = "xlsx"
    PPTX = "pptx"


class DocumentScope(str, Enum):
    GLOBAL = "global"
    WORKSPACE = "workspace"


class DocumentVersionStatus(str, Enum):
    PENDING = "pending"
    UPLOADED = "uploaded"
    SECURITY_PENDING = "security_pending"
    SECURITY_RUNNING = "security_running"
    SECURITY_FAILED = "security_failed"
    INGESTING = "ingesting"
    PROCESSING_FAILED = "processing_failed"
    AVAILABLE = "available"
    QUARANTINED = "quarantined"
    ABORTED = "aborted"


class Document(Base, AuditMixin):
    """Document model."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspaceId: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    scope: Mapped[DocumentScope] = mapped_column(
        SAEnum(DocumentScope, name="document_scope", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    organizationId: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    document_name: Mapped[str] = mapped_column(String(500), nullable=False)

    # Relationships disabled - document_service uses separate DB
    # versions: Mapped[list["DocumentVersion"]] = relationship(
    #     "DocumentVersion", back_populates="document", cascade="all, delete-orphan"
    # )

    __table_args__ = (
        Index("ix_documents_organization", "organizationId"),
        Index("ix_documents_workspace", "workspaceId"),
    )


class DocumentVersion(Base, AuditMixin):
    """Document version model."""

    __tablename__ = "document_versions"

    versionId: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    documentId: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[DocumentVersionStatus] = mapped_column(
        SAEnum(DocumentVersionStatus, name="document_version_status", values_callable=lambda e: [m.value for m in e]),
        default=DocumentVersionStatus.PENDING,
        nullable=False,
    )
    objectKey: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploadId: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    fileSize: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    mediaType: Mapped[MediaType] = mapped_column(
        SAEnum(MediaType, name="media_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    workspaceId: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    quarantine_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(default=0, nullable=False)

    # Relationships disabled - document_service uses separate DB
    # document: Mapped["Document"] = relationship("Document", back_populates="versions")

    __table_args__ = (
        Index("ix_document_versions_document", "documentId"),
        Index("ix_document_versions_status", "status"),
        Index("ix_document_versions_idempotency", "idempotency_key"),
    )