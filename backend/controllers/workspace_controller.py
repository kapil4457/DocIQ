import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database.db_engine import get_db
from dto.request.create_workspace import CreateWorkspaceRequest
from dto.request.update_workspace import UpdateWorkspaceRequest
from dto.request.add_workspace_member import AddWorkspaceMemberRequest
from dto.response.get_workspaces import GetAllWorkspacesResponse, WorkspaceResponse
from dto.response.get_workspace_members import GetWorkspaceMembersResponse
from dto.response.get_workspace import GetWorkspaceResponse
from dto.response.base_response import BaseResponse
from services.workspace_service import (
    create_workspace_handler,
    get_workspace_handler,
    get_all_workspaces_handler,
    update_workspace_handler,
    delete_workspace_handler,
    get_workspace_members_handler,
    add_workspace_member_handler,
    remove_workspace_member_handler,
)
from utils.auth_dependencies import CurrentUser

router = APIRouter(prefix="/workspace", tags=["Workspace"])


@router.post("/create", response_model=GetWorkspaceResponse)
def create_workspace(
    request: CreateWorkspaceRequest,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    result = create_workspace_handler(db, request, user)
    return GetWorkspaceResponse(**result, message="Workspace created successfully")


@router.get("/list", response_model=GetAllWorkspacesResponse)
def get_workspaces(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    pageSize: int = Query(9, ge=1, le=100),
):
    result = get_all_workspaces_handler(db, user, page, pageSize)
    return GetAllWorkspacesResponse(
        workspaces=[WorkspaceResponse(**ws) for ws in result["workspaces"]],
        total=result["total"],
        page=result["page"],
        pageSize=result["pageSize"],
        message="Workspaces fetched successfully",
    )


@router.get("/{workspace_id}", response_model=GetWorkspaceResponse)
def get_workspace(
    workspace_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    result = get_workspace_handler(db, workspace_id, user)
    return GetWorkspaceResponse(**result, message="Workspace fetched successfully")


@router.patch("/{workspace_id}", response_model=BaseResponse)
def update_workspace(
    workspace_id: uuid.UUID,
    request: UpdateWorkspaceRequest,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    workspace = update_workspace_handler(db, workspace_id, request, user)
    return BaseResponse(message=workspace.name)


@router.delete("/{workspace_id}", response_model=BaseResponse)
def delete_workspace(
    workspace_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    return BaseResponse(**delete_workspace_handler(db, workspace_id, user))


@router.get("/{workspace_id}/members", response_model=GetWorkspaceMembersResponse)
def get_workspace_members(
    workspace_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    result = get_workspace_members_handler(db, workspace_id, user)
    return GetWorkspaceMembersResponse(**result)


@router.post("/{workspace_id}/members", response_model=BaseResponse)
def add_workspace_member(
    workspace_id: uuid.UUID,
    request: AddWorkspaceMemberRequest,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    return BaseResponse(**add_workspace_member_handler(db, workspace_id, request.email, user))


@router.delete("/{workspace_id}/members/{member_user_id}", response_model=BaseResponse)
def remove_workspace_member(
    workspace_id: uuid.UUID,
    member_user_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    return BaseResponse(**remove_workspace_member_handler(db, workspace_id, member_user_id, user))
