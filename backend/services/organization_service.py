import logging
import secrets

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from database.models.organization import Organization
from database.models.user import User, UserRole
from dto.request.create_organization import CreateOrganizationRequest
from dto.response.create_organization import CreateOrganizationResponse
from utils.security import hash_password
from utils.exception_handler import ConflictError, NotFoundError
from services.shared import log_event, conflict, paginate

logger = logging.getLogger("app.services.organization")

TEMP_PASSWORD_LENGTH = 12


def create_organization_handler(db: Session, request: CreateOrganizationRequest, current_user) -> CreateOrganizationResponse:
    conflict(
        db.scalar(select(Organization).where(Organization.name == request.name)) is not None,
        f"An organization named '{request.name}' already exists",
        logger,
        name=request.name,
    )

    organization = Organization(
        **request.model_dump(),
        createdBy=current_user.id,
        modifiedBy=current_user.id,
    )
    db.add(organization)
    db.flush()

    temp_password = secrets.token_urlsafe(TEMP_PASSWORD_LENGTH)[:TEMP_PASSWORD_LENGTH]
    org_super_admin = User(
        name=f"{request.name} Admin",
        email=request.supportEmail,
        password=hash_password(temp_password),
        organizationId=organization.id,
        role=UserRole.ORG_SUPER_ADMIN,
        createdBy=current_user.id,
        modifiedBy=current_user.id,
    )
    db.add(org_super_admin)
    db.commit()
    db.refresh(organization)
    log_event(
        logger,
        "Organization created with org super admin",
        organizationId=organization.id,
        orgSuperAdminId=org_super_admin.id,
        createdBy=str(current_user.id),
    )

    response = CreateOrganizationResponse.model_validate(organization)
    response.message = "Organization created successfully"
    response.tempPassword = temp_password
    response.orgSuperAdminEmail = org_super_admin.email
    return response


def update_organization_handler(db: Session, organization_id, request, current_user) -> dict:
    organization = db.get(Organization, organization_id)
    if organization is None:
        raise NotFoundError("Organization not found")

    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(organization, field, value)
    organization.modifiedBy = current_user.id
    db.commit()
    db.refresh(organization)
    log_event(
        logger,
        "Organization updated",
        organizationId=organization_id,
        updatedBy=str(current_user.id),
    )
    return organization


def reset_org_super_admin_credentials_handler(db: Session, organization_id, current_user) -> dict:
    org_super_admin = db.scalar(
        select(User).where(
            User.organizationId == organization_id,
            User.role == UserRole.ORG_SUPER_ADMIN,
        )
    )
    if org_super_admin is None:
        raise NotFoundError("This organization has no org super admin")

    temp_password = secrets.token_urlsafe(TEMP_PASSWORD_LENGTH)[:TEMP_PASSWORD_LENGTH]
    org_super_admin.password = hash_password(temp_password)
    org_super_admin.modifiedBy = current_user.id
    db.commit()
    log_event(
        logger,
        "Org super admin credentials reset",
        organizationId=organization_id,
        userId=org_super_admin.id,
        resetBy=str(current_user.id),
    )
    return {
        "email": org_super_admin.email,
        "temporaryPassword": temp_password,
        "message": "Credentials reset. Share this password through a secure channel; it will not be shown again.",
    }


def get_all_organizations_handler(db: Session, page: int, page_size: int) -> dict:
    result = paginate(
        db,
        select(Organization).order_by(Organization.createdAt.desc()),
        select(func.count()).select_from(Organization),
        page,
        page_size,
    )

    member_counts = {
        org_id: count
        for org_id, count in db.execute(
            select(User.organizationId, func.count())
            .where(User.organizationId.isnot(None))
            .group_by(User.organizationId)
        ).all()
    }

    return {
        "organizations": [
            {
                "id": org.id,
                "name": org.name,
                "supportEmail": org.supportEmail,
                "memberCount": member_counts.get(org.id, 0),
                "message": "",
                "code": 200,
            }
            for org in result["items"]
        ],
        "total": result["total"],
        "page": result["page"],
        "pageSize": result["pageSize"],
    }
