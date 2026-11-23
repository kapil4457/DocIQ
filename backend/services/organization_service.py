import uuid
from dto.request.create_organization import CreateOrganizationRequest
from dto.request.update_organization import UpdateOrganizationRequest
from dto.response.create_organization import CreateOrganizationResponse
from database.models.organization import Organization
from sqlalchemy.orm import Session
from dto.response.get_organizations import GetAllOrganizationResponse, Organization as OrganizationResponse
from database.models.organization import Organization as OrganizationModel
from dto.response.delete_response import DeleteResponse
from sqlalchemy import select


def create_organization_handler(db: Session, request: CreateOrganizationRequest)-> CreateOrganizationResponse:
    organization: Organization = Organization(**request.model_dump())    

    db.add(organization)
    db.commit()
    db.refresh(organization)

    response = CreateOrganizationResponse.model_validate(organization)
    response.message = "Organization created successfully"
    return response


def get_all_organization_handler(db: Session) -> GetAllOrganizationResponse:
    organizations = db.scalars(select(OrganizationModel)).all()

    response = GetAllOrganizationResponse(organizations=organizations)
    response.message = "Organizations fetched successfully"
    return response


def get_organization_handler(db: Session, organization_id: uuid.UUID) -> OrganizationResponse:
    organization = db.get(OrganizationModel, organization_id)
    if organization is None:
        raise ValueError("Organization not found")
    response = OrganizationResponse.model_validate(organization)
    response.message = "Organization fetched successfully"
    return response


def update_organization_handler(db: Session, organization_id: uuid.UUID, request: UpdateOrganizationRequest) -> OrganizationResponse:
    organization = db.get(OrganizationModel, organization_id)
    if organization is None:
        raise ValueError("Organization not found")
    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(organization, field, value)
    db.commit()
    db.refresh(organization)
    response = OrganizationResponse.model_validate(organization)
    response.message = "Organization updated successfully"
    return response


def delete_organization_handler(db: Session, organization_id: uuid.UUID) -> DeleteResponse:
    organization = db.get(OrganizationModel, organization_id)
    if organization is None:
        raise ValueError("Organization not found")
    db.delete(organization)
    db.commit()
    return DeleteResponse(message="Organization deleted successfully")