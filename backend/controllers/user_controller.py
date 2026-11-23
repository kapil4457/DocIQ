import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database.db_engine import get_db
from dto.request.create_organization_user import CreateOrganizationUserRequest
from dto.request.update_user_role import UpdateUserRoleRequest
from dto.request.login_user import LoginUserRequest
from dto.request.refresh_token import RefreshTokenRequest
from dto.response.create_user import CreateUserResponse
from dto.response.get_organization_users import GetOrganizationUsersResponse
from dto.response.reset_credentials import ResetCredentialsResponse
from services.user_service import (
    create_organization_user_handler,
    get_organization_users_handler,
    update_organization_user_role_handler,
    delete_organization_user_handler,
    reset_organization_user_credentials_handler,
    login_handler,
    refresh_token_handler,
)
from utils.auth_dependencies import OrgSuperAdminDependency

router = APIRouter(prefix="/user", tags=["User"])


@router.post("/login")
def login(request: LoginUserRequest, db: Annotated[Session, Depends(get_db)]):
    return login_handler(db, request)


@router.post("/refresh")
def refresh_token(request: RefreshTokenRequest, db: Annotated[Session, Depends(get_db)]):
    return refresh_token_handler(db, request)


@router.post("/organization/{organization_id}/users", response_model=CreateUserResponse)
def add_user_to_organization(
    organization_id: uuid.UUID,
    request: CreateOrganizationUserRequest,
    user: OrgSuperAdminDependency,
    db: Annotated[Session, Depends(get_db)],
):
    return create_organization_user_handler(db, organization_id, request, user)


@router.get("/organization/{organization_id}/users", response_model=GetOrganizationUsersResponse)
def get_organization_users(
    organization_id: uuid.UUID,
    user: OrgSuperAdminDependency,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1, le=100),
):
    return get_organization_users_handler(db, organization_id, page, pageSize)


@router.patch("/organization/{organization_id}/users/{user_id}/role", response_model=CreateUserResponse)
def update_organization_user_role(
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    request: UpdateUserRoleRequest,
    user: OrgSuperAdminDependency,
    db: Annotated[Session, Depends(get_db)],
):
    return update_organization_user_role_handler(db, organization_id, user_id, request, user)


@router.delete("/organization/{organization_id}/users/{user_id}")
def delete_organization_user(
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    user: OrgSuperAdminDependency,
    db: Annotated[Session, Depends(get_db)],
):
    return delete_organization_user_handler(db, organization_id, user_id, user)


@router.post("/organization/{organization_id}/users/{user_id}/reset-credentials", response_model=ResetCredentialsResponse)
def reset_organization_user_credentials(
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    user: OrgSuperAdminDependency,
    db: Annotated[Session, Depends(get_db)],
):
    return reset_organization_user_credentials_handler(db, organization_id, user_id, user)
