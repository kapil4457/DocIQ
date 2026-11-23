"""Shared helpers used across services: audit-safe commits, logging, pagination, access checks."""

import logging
from typing import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models.user import User, UserRole
from utils.exception_handler import ConflictError, ForbiddenError, NotFoundError

logger = logging.getLogger("app.services.shared")


def log_event(event_logger: logging.Logger, message: str, level: int = logging.INFO, **data) -> None:
    """Emit a structured log line through the app's extra_data channel."""
    event_logger.log(level, message, extra={"extra_data": data})


def forbid(condition: bool, message: str, event_logger: logging.Logger | None = None, **data) -> None:
    """Raise ForbiddenError when the condition holds, logging a warning first."""
    if condition:
        if event_logger:
            log_event(event_logger, message, level=logging.WARNING, **data)
        raise ForbiddenError(message)


def not_found(condition: bool, message: str, event_logger: logging.Logger | None = None, **data) -> None:
    """Raise NotFoundError when the condition holds, logging a warning first."""
    if condition:
        if event_logger:
            log_event(event_logger, message, level=logging.WARNING, **data)
        raise NotFoundError(message)


def conflict(condition: bool, message: str, event_logger: logging.Logger | None = None, **data) -> None:
    """Raise ConflictError when the condition holds, logging a warning first."""
    if condition:
        if event_logger:
            log_event(event_logger, message, level=logging.WARNING, **data)
        raise ConflictError(message)


def get_or_404(db: Session, model, entity_id, event_logger: logging.Logger | None = None, message: str | None = None):
    """Fetch an entity by primary key or raise NotFoundError."""
    entity = db.get(model, entity_id)
    not_found(entity is None, message or f"{model.__name__} not found", event_logger, id=str(entity_id))
    return entity


def paginate(
    db: Session,
    stmt,
    count_stmt,
    page: int,
    page_size: int,
    transform: Callable | None = None,
) -> dict:
    """Apply offset/limit to a statement and return the standard page envelope."""
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [transform(row) for row in rows] if transform else rows
    return {"items": items, "total": total, "page": page, "pageSize": page_size}


def count_by(db: Session, model, column, value) -> int:
    return db.scalar(select(func.count()).select_from(model).where(column == value)) or 0


def assert_super_admin_cannot_upload(user) -> None:
    forbid(user.role == UserRole.SUPER_ADMIN, "Super admins cannot upload documents")


def assert_can_manage_organization_docs(user, organization_id) -> None:
    forbid(
        user.organizationId != organization_id,
        "You can only manage documents in your own organization",
    )
