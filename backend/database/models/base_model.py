from datetime import datetime, timezone
import uuid
from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class AuditMixin:
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    createdBy: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    modifiedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    modifiedBy: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
