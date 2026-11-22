from fastapi import APIRouter,status, Response
from dto.request.create_organization import CreateOrganizationRequest
from dto.response.create_organization import CreateOrganizationResponse
router = APIRouter(prefix="/organization",tags=["Organization"])

@router.post("/create")
async def create_organization(request: CreateOrganizationRequest) -> CreateOrganizationResponse:
    pass

@router.get("/list")
async def get_organizations():
    pass


@router.get("/{organization_id}")
async def get_organization_by_id(organization_id: str):
    pass