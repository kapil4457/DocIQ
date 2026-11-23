from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database.db_engine import get_db
from dto.request.create_organization import CreateOrganizationRequest
from dto.response.create_organization import CreateOrganizationResponse
from dto.response.get_organizations import GetAllOrganizationResponse
from services.organization_service import create_organization_handler, get_all_organizations_handler
from utils.auth_dependencies import SuperAdmin

router = APIRouter(prefix="/organization", tags=["Organization"])


@router.post("/create", response_model=CreateOrganizationResponse)
def create_organization(
    request: CreateOrganizationRequest,
    user: SuperAdmin,
    db: Annotated[Session, Depends(get_db)],
):
    return create_organization_handler(db, request)


@router.get("/list", response_model=GetAllOrganizationResponse)
def get_organizations(
    user: SuperAdmin,
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1, le=100),
):
    result = get_all_organizations_handler(db, page, pageSize)
    return GetAllOrganizationResponse(**result)
