import uuid
import logging

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from database.models.user import User
from database.models.organization import Organization
from dto.request.create_user import CreateUserRequest
from dto.request.create_organization_user import CreateOrganizationUserRequest
from dto.request.login_user import LoginUserRequest
from dto.response.create_user import CreateUserResponse
from utils.security import hash_password, verify_password
from utils.jwt_handler import create_access_token, create_refresh_token, decode_token
from utils.exception_handler import ConflictError, NotFoundError, UnauthorizedError
from services.shared import log_event, conflict, get_or_404, count_by, paginate

logger = logging.getLogger("app.services.user")


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


def create_user_handler(db: Session, request: CreateUserRequest) -> CreateUserResponse:
    _assert_email_available(db, request.email)

    data = request.model_dump()
    data["password"] = hash_password(request.password)
    user = User(**data)
    db.add(user)
    db.commit()
    db.refresh(user)
    response = CreateUserResponse.model_validate(user)
    response.message = "User created successfully"
    return response


def create_organization_user_handler(
    db: Session, organization_id: uuid.UUID, request: CreateOrganizationUserRequest
) -> CreateUserResponse:
    get_or_404(db, Organization, organization_id, logger, "Organization not found")
    _assert_email_available(db, request.email)

    user = User(
        name=request.name,
        email=request.email,
        password=hash_password(request.password),
        organizationId=organization_id,
        role=request.role,
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


def delete_organization_user_handler(db: Session, organization_id: uuid.UUID, user_id: uuid.UUID) -> dict:
    user = db.get(User, user_id)
    if user is None or user.organizationId != organization_id:
        raise NotFoundError("User not found in this organization")
    db.delete(user)
    db.commit()
    log_event(
        logger,
        "Organization user deleted",
        userId=user_id,
        organizationId=organization_id,
    )
    return {"message": "User deleted successfully"}


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
