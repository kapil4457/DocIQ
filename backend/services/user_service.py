import uuid
import logging
import secrets

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from database.models.user import User, UserRole
from database.models.organization import Organization
from dto.request.create_user import CreateUserRequest
from dto.request.create_organization_user import CreateOrganizationUserRequest
from dto.request.update_user_role import UpdateUserRoleRequest
from dto.request.login_user import LoginUserRequest
from dto.response.create_user import CreateUserResponse
from utils.security import hash_password, verify_password
from utils.jwt_handler import create_access_token, create_refresh_token, decode_token
from utils.exception_handler import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError
from services.shared import log_event, conflict, get_or_404, paginate

logger = logging.getLogger("app.services.user")

TEMP_PASSWORD_LENGTH = 12


def _assert_email_available(db: Session, email: str) -> None:
    conflict(
        db.scalar(select(User).where(User.email == email)) is not None,
        f"A user with email {email} already exists",
        logger,
        email=email,
    )


def _build_auth_payload(user: User, message: str) -> dict:
    return {
        "userId": str(user.id),
        "name": user.name,
        "email": user.email,
        "organizationId": str(user.organizationId) if user.organizationId else None,
        "role": user.role.value,
        "accessToken": create_access_token(str(user.id), user.role.value),
        "refreshToken": create_refresh_token(str(user.id)),
        "message": message,
    }


def create_user_handler(db: Session, request: CreateUserRequest, current_user=None) -> CreateUserResponse:
    _assert_email_available(db, request.email)

    data = request.model_dump()
    data["password"] = hash_password(request.password)
    if current_user is not None:
        data["createdBy"] = current_user.id
        data["modifiedBy"] = current_user.id
    user = User(**data)
    db.add(user)
    db.commit()
    db.refresh(user)
    response = CreateUserResponse.model_validate(user)
    response.message = "User created successfully"
    return response


def create_organization_user_handler(
    db: Session, organization_id: uuid.UUID, request: CreateOrganizationUserRequest, current_user
) -> CreateUserResponse:
    get_or_404(db, Organization, organization_id, logger, "Organization not found")
    _assert_email_available(db, request.email)

    user = User(
        name=request.name,
        email=request.email,
        password=hash_password(request.password),
        organizationId=organization_id,
        role=request.role,
        createdBy=current_user.id,
        modifiedBy=current_user.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_event(
        logger,
        "Organization user created",
        userId=user.id,
        organizationId=organization_id,
        role=request.role.value,
        createdBy=str(current_user.id),
    )
    response = CreateUserResponse.model_validate(user)
    response.message = "User added to organization successfully"
    return response


def get_organization_users_handler(
    db: Session, organization_id: uuid.UUID, page: int, page_size: int
) -> dict:
    get_or_404(db, Organization, organization_id, logger, "Organization not found")

    base = select(User).where(User.organizationId == organization_id)
    result = paginate(
        db,
        base.order_by(User.createdAt.desc()),
        select(func.count()).select_from(User).where(User.organizationId == organization_id),
        page,
        page_size,
    )
    return {
        "users": result["items"],
        "total": result["total"],
        "page": result["page"],
        "pageSize": result["pageSize"],
    }


def update_organization_user_role_handler(
    db: Session, organization_id: uuid.UUID, user_id: uuid.UUID, request: UpdateUserRoleRequest, current_user
) -> CreateUserResponse:
    user = db.get(User, user_id)
    if user is None or user.organizationId != organization_id:
        raise NotFoundError("User not found in this organization")

    if user.id == current_user.id:
        raise ForbiddenError("You cannot change your own role")

    if user.role not in (UserRole.PARTICIPANT, UserRole.ORG_ADMIN):
        raise ForbiddenError("Only participant and org_admin roles can be toggled")

    old_role = user.role
    user.role = request.role
    user.modifiedBy = current_user.id
    db.commit()
    db.refresh(user)
    log_event(
        logger,
        "Organization user role updated",
        userId=user.id,
        organizationId=organization_id,
        oldRole=old_role.value,
        newRole=user.role.value,
        updatedBy=str(current_user.id),
    )
    response = CreateUserResponse.model_validate(user)
    response.message = "User role updated successfully"
    return response


def delete_organization_user_handler(
    db: Session, organization_id: uuid.UUID, user_id: uuid.UUID, current_user
) -> dict:
    user = db.get(User, user_id)
    if user is None or user.organizationId != organization_id:
        raise NotFoundError("User not found in this organization")

    if user.id == current_user.id:
        raise ForbiddenError("You cannot delete your own account")

    if user.role == UserRole.ORG_SUPER_ADMIN:
        raise ForbiddenError("The organization super admin account cannot be deleted")

    db.delete(user)
    db.commit()
    log_event(
        logger,
        "Organization user deleted",
        userId=user_id,
        organizationId=organization_id,
        deletedBy=str(current_user.id),
    )
    return {"message": "User deleted successfully"}


def reset_organization_user_credentials_handler(
    db: Session, organization_id: uuid.UUID, user_id: uuid.UUID, current_user
) -> dict:
    user = db.get(User, user_id)
    if user is None or user.organizationId != organization_id:
        raise NotFoundError("User not found in this organization")

    temp_password = secrets.token_urlsafe(TEMP_PASSWORD_LENGTH)[:TEMP_PASSWORD_LENGTH]
    user.password = hash_password(temp_password)
    user.modifiedBy = current_user.id
    db.commit()
    log_event(
        logger,
        "Organization user credentials reset",
        userId=user.id,
        organizationId=organization_id,
        resetBy=str(current_user.id),
    )
    return {
        "email": user.email,
        "temporaryPassword": temp_password,
        "message": "Credentials reset. Share this password through a secure channel; it will not be shown again.",
    }


def refresh_token_handler(db: Session, request) -> dict:
    try:
        payload = decode_token(request.refreshToken, expected_type="refresh")
    except ValueError as exc:
        raise UnauthorizedError(str(exc)) from exc

    user = db.get(User, uuid.UUID(payload["sub"]))
    if user is None:
        raise UnauthorizedError("User no longer exists")

    log_event(logger, "Token refreshed", userId=user.id)
    return _build_auth_payload(user, "Token refreshed successfully")


def login_handler(db: Session, request: LoginUserRequest) -> dict:
    user = db.scalar(select(User).where(User.email == request.email))
    if user is None or not verify_password(request.password, user.password):
        log_event(logger, "Failed login attempt", level=logging.WARNING, email=request.email)
        raise UnauthorizedError("Incorrect email or password")

    log_event(logger, "User logged in", userId=user.id)
    return _build_auth_payload(user, "Logged in successfully")
