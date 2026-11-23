from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database.db_engine import get_db
from dto.request.create_organization import CreateOrganizationRequest
from dto.response.create_organization import CreateOrganizationResponse
from services.organization_service import create_organization_handler

router = APIRouter(prefix="/organization", tags=["Organization"])


@router.post("/create", response_model=CreateOrganizationResponse)
def create_organization(request: CreateOrganizationRequest, db: Session = Depends(get_db)):
    return create_organization_handler(db, request)
