from uuid import UUID
from pydantic import ConfigDict, EmailStr, Field
from dto.response.base_response import BaseResponse


class Organization(BaseResponse):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    id: UUID = Field(..., description="ID of the organization")
    name: str = Field(..., description="Name of the organization")
    supportEmail: EmailStr = Field(..., description="Support email of the organization")
    memberCount: int = Field(0, description="Number of users in the organization")


class GetAllOrganizationResponse(BaseResponse):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    organizations: list[Organization] = Field(..., description="Page of organizations")
    total: int = Field(..., description="Total number of organizations")
    page: int = Field(..., description="Current page number")
    pageSize: int = Field(..., description="Number of items per page")
