import uuid
import logging

from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import Session

from database.models.user import User, UserRole
from database.models.workspace import Workspace, WorkspaceMember
from database.models.organization import Organization
from dto.request.create_workspace import CreateWorkspaceRequest
from dto.request.update_workspace import UpdateWorkspaceRequest
from utils.exception_handler import ConflictError, ForbiddenError, NotFoundError
from services.shared import log_event, conflict, get_or_404, paginate

logger = logging.getLogger("app.services.workspace")


def get_workspace_or_404(db: Session, workspace_id: uuid.UUID) -> Workspace:
    return get_or_404(db, Workspace, workspace_id, logger, "Workspace not found")


def assert_workspace_access(db: Session, workspace: Workspace, user) -> None:
    """Any org member who is the creator or an explicit member may enter."""
    if user.role == UserRole.SUPER_ADMIN:
        raise ForbiddenError("Super admins do not have access to workspaces")
    if user.organizationId != workspace.organizationId:
        raise ForbiddenError("You do not have access to this workspace")
    if workspace.userId == user.id:
        return
    is_member = db.scalar(
        select(func.count()).select_from(WorkspaceMember).where(
            WorkspaceMember.workspaceId == workspace.id,
            WorkspaceMember.userId == user.id,
        )
    )
    if not is_member:
        raise ForbiddenError("You do not have access to this workspace")


def assert_workspace_admin(db: Session, workspace: Workspace, user) -> None:
    """Creator or org super admin may rename, delete, share."""
    if user.role == UserRole.ORG_SUPER_ADMIN and user.organizationId == workspace.organizationId:
        return
    if workspace.userId == user.id:
        return
    raise ForbiddenError("Only the workspace creator or the organization super admin can manage this workspace")


def create_workspace_handler(db: Session, request: CreateWorkspaceRequest, current_user) -> dict:
    if current_user.role == UserRole.SUPER_ADMIN:
        raise ForbiddenError("Super admins cannot create workspaces")
    if current_user.organizationId is None:
        raise ForbiddenError("You must belong to an organization to create workspaces")

    duplicate = db.scalar(
        select(Workspace).where(
            Workspace.organizationId == current_user.organizationId,
            Workspace.name == request.name,
        )
    )
    conflict(duplicate is not None, f"A workspace named '{request.name}' already exists", logger, name=request.name)

    workspace = Workspace(
        name=request.name,
        userId=current_user.id,
        organizationId=current_user.organizationId,
        createdBy=current_user.id,
        modifiedBy=current_user.id,
    )
    db.add(workspace)
    db.flush()
    db.add(WorkspaceMember(
        workspaceId=workspace.id,
        userId=current_user.id,
        createdBy=current_user.id,
        modifiedBy=current_user.id,
    ))
    db.commit()
    db.refresh(workspace)
    log_event(
        logger, "Workspace created",
        workspaceId=workspace.id,
        organizationId=workspace.organizationId,
        createdBy=str(current_user.id),
    )
    return workspace


def get_workspace_handler(db: Session, workspace_id: uuid.UUID, current_user) -> Workspace:
    workspace = get_workspace_or_404(db, workspace_id)
    assert_workspace_access(db, workspace, current_user)
    return workspace


def get_all_workspaces_handler(db: Session, current_user, page: int, page_size: int) -> dict:
    if current_user.organizationId is None:
        raise ForbiddenError("You must belong to an organization to have workspaces")

    org_filter = Workspace.organizationId == current_user.organizationId
    access_filter = or_(
        Workspace.userId == current_user.id,
        Workspace.id.in_(
            select(WorkspaceMember.workspaceId).where(WorkspaceMember.userId == current_user.id)
        ),
    )
    base = select(Workspace).where(and_(org_filter, access_filter))
    count_stmt = select(func.count()).select_from(Workspace).where(and_(org_filter, access_filter))
    result = paginate(db, base.order_by(Workspace.createdAt.desc()), count_stmt, page, page_size)

    member_counts = {
        ws_id: count
        for ws_id, count in db.execute(
            select(WorkspaceMember.workspaceId, func.count())
            .where(WorkspaceMember.workspaceId.in_([w.id for w in result["items"]] or [None]))
            .group_by(WorkspaceMember.workspaceId)
        ).all()
    } if result["items"] else {}

    return {
        "workspaces": [
            {
                "id": ws.id,
                "name": ws.name,
                "creatorId": ws.userId,
                "memberCount": member_counts.get(ws.id, 1),
            }
            for ws in result["items"]
        ],
        "total": result["total"],
        "page": result["page"],
        "pageSize": result["pageSize"],
    }


def update_workspace_handler(db: Session, workspace_id: uuid.UUID, request: UpdateWorkspaceRequest, current_user) -> Workspace:
    workspace = get_workspace_or_404(db, workspace_id)
    assert_workspace_access(db, workspace, current_user)
    assert_workspace_admin(db, workspace, current_user)

    if request.name is not None:
        duplicate = db.scalar(
            select(Workspace).where(
                Workspace.organizationId == workspace.organizationId,
                Workspace.name == request.name,
                Workspace.id != workspace.id,
            )
        )
        conflict(duplicate is not None, f"A workspace named '{request.name}' already exists", logger, name=request.name)
        workspace.name = request.name
        workspace.modifiedBy = current_user.id
        db.commit()
        db.refresh(workspace)
        log_event(logger, "Workspace renamed", workspaceId=workspace.id, updatedBy=str(current_user.id))
    return workspace


def delete_workspace_handler(db: Session, workspace_id: uuid.UUID, current_user) -> dict:
    workspace = get_workspace_or_404(db, workspace_id)
    assert_workspace_access(db, workspace, current_user)
    assert_workspace_admin(db, workspace, current_user)

    db.delete(workspace)
    db.commit()
    log_event(logger, "Workspace deleted", workspaceId=workspace_id, deletedBy=str(current_user.id))
    return {"message": "Workspace deleted successfully"}


def get_workspace_members_handler(db: Session, workspace_id: uuid.UUID, current_user) -> dict:
    workspace = get_workspace_or_404(db, workspace_id)
    assert_workspace_access(db, workspace, current_user)

    member_rows = db.execute(
        select(User, WorkspaceMember)
        .join(WorkspaceMember, WorkspaceMember.userId == User.id)
        .where(WorkspaceMember.workspaceId == workspace.id)
        .order_by(WorkspaceMember.createdAt.asc())
    ).all()

    members = [
        {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role.value,
            "isCreator": user.id == workspace.userId,
        }
        for user, _membership in member_rows
    ]
    return {"members": members, "total": len(members)}


def add_workspace_member_handler(db: Session, workspace_id: uuid.UUID, email: str, current_user) -> dict:
    workspace = get_workspace_or_404(db, workspace_id)
    assert_workspace_access(db, workspace, current_user)
    assert_workspace_admin(db, workspace, current_user)

    target = db.scalar(select(User).where(User.email == email))
    if target is None or target.organizationId != workspace.organizationId:
        raise NotFoundError(f"No user with email {email} in this organization")

    existing = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspaceId == workspace.id,
            WorkspaceMember.userId == target.id,
        )
    )
    conflict(existing is not None, f"{target.name} is already a member of this workspace", logger, email=email)

    db.add(WorkspaceMember(
        workspaceId=workspace.id,
        userId=target.id,
        createdBy=current_user.id,
        modifiedBy=current_user.id,
    ))
    db.commit()
    log_event(
        logger, "Workspace member added",
        workspaceId=workspace.id,
        userId=target.id,
        addedBy=str(current_user.id),
    )
    return {"message": f"{target.name} added to workspace", "userId": target.id}


def remove_workspace_member_handler(db: Session, workspace_id: uuid.UUID, member_user_id: uuid.UUID, current_user) -> dict:
    workspace = get_workspace_or_404(db, workspace_id)
    assert_workspace_access(db, workspace, current_user)
    assert_workspace_admin(db, workspace, current_user)

    if member_user_id == workspace.userId:
        raise ForbiddenError("The workspace creator cannot be removed")

    membership = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspaceId == workspace.id,
            WorkspaceMember.userId == member_user_id,
        )
    )
    if membership is None:
        raise NotFoundError("User is not a member of this workspace")

    db.delete(membership)
    db.commit()
    log_event(
        logger, "Workspace member removed",
        workspaceId=workspace.id,
        userId=member_user_id,
        removedBy=str(current_user.id),
    )
    return {"message": "Member removed from workspace"}
