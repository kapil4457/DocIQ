from uuid import UUID
from pydantic import ConfigDict, EmailStr, Field
from dto.response.base_response import BaseResponse
from database.models.user import UserRole


class OrganizationUser(BaseResponse):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    id: UUID = Field(..., description="ID of the user")
    name: str = Field(..., description="Name of the user")
    email: EmailStr = Field(..., description="Email of the user")
    role: UserRole = Field(..., description="Role of the user")


class GetOrganizationUsersResponse(BaseResponse):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    users: list[OrganizationUser] = Field(..., description="Page of users in the organization")
    total: int = Field(..., description="Total number of users in the organization")
    page: int = Field(..., description="Current page number")
    pageSize: int = Field(..., description="Number of items per page")
