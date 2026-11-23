import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from database.db_engine import get_db
from database.models.user import User, UserRole
from utils.jwt_handler import decode_token
from utils.exception_handler import UnauthorizedError, ForbiddenError

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None:
        raise UnauthorizedError("Authentication required")

    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except ValueError as exc:
        raise UnauthorizedError(str(exc)) from exc

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise UnauthorizedError("Malformed token subject") from exc

    user = db.get(User, user_id)
    if user is None:
        raise UnauthorizedError("User no longer exists")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_super_admin(user: CurrentUser) -> User:
    if user.role != UserRole.SUPER_ADMIN:
        raise ForbiddenError("Super admin access required")
    return user


SuperAdmin = Annotated[User, Depends(require_super_admin)]


def require_org_super_admin(organization_id: uuid.UUID, user: CurrentUser) -> User:
    if user.role != UserRole.ORG_SUPER_ADMIN or user.organizationId != organization_id:
        raise ForbiddenError("Organization super admin access required")
    return user


def _org_super_admin(
    organization_id: uuid.UUID,
    user: CurrentUser,
) -> User:
    return require_org_super_admin(organization_id, user)


OrgSuperAdminDependency = Annotated[User, Depends(_org_super_admin)]
