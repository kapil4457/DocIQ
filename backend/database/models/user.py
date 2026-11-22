from enum import Enum
import uuid
from sqlalchemy import Enum as SAEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from database.models.base_model import Base
from typing import Optional


class UserRole(str, Enum):
    PARTICIPANT = "participant"
    ORG_ADMIN = "org_admin"
    SUPER_ADMIN = "super_admin"

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    organizationId: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole, name="user_role"), nullable=False)
