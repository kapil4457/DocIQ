from uuid import UUID
from typing import Optional
from pydantic import ConfigDict, EmailStr, Field
from dto.response.base_response import BaseResponse
from database.models.user import UserRole


class CreateUserResponse(BaseResponse):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    userId: UUID = Field(
        ...,
        validation_alias="id",
        description="ID of the created user",
    )
    name: str = Field(..., description="Name of the user")
    email: EmailStr = Field(..., description="Email of the user")
    organizationId: Optional[UUID] = Field(None, description="Organization of the user")
    role: UserRole = Field(..., description="Role of the user")
