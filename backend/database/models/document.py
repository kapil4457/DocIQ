from enum import Enum
from typing import Optional
import uuid
from sqlalchemy import Enum as SAEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from database.models.base_model import Base


class Scope(str, Enum):
    WORKSPACE = "workspace"
    GLOBAL = "global"

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspaceId: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True
    )
    scope: Mapped[Scope] = mapped_column(
        SAEnum(Scope, name="document_scope", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    organizationId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    document_name: Mapped[str] = mapped_column(String(500), nullable=False)
