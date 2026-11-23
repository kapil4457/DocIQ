import logging

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from database.models.organization import Organization
from database.models.user import User
from dto.request.create_organization import CreateOrganizationRequest
from dto.response.create_organization import CreateOrganizationResponse
from utils.exception_handler import ConflictError
from services.shared import log_event, conflict, paginate

logger = logging.getLogger("app.services.organization")


def create_organization_handler(db: Session, request: CreateOrganizationRequest) -> CreateOrganizationResponse:
    conflict(
        db.scalar(select(Organization).where(Organization.name == request.name)) is not None,
        f"An organization named '{request.name}' already exists",
        logger,
        name=request.name,
    )

    organization = Organization(**request.model_dump())
    db.add(organization)
    db.commit()
    db.refresh(organization)
    log_event(logger, "Organization created", organizationId=organization.id)

    response = CreateOrganizationResponse.model_validate(organization)
    response.message = "Organization created successfully"
    return response


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
