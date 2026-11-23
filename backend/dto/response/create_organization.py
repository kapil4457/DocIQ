from uuid import UUID
from typing import Optional
from pydantic import ConfigDict, EmailStr, Field
from dto.response.base_response import BaseResponse


class CreateOrganizationResponse(BaseResponse):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    organizationId: UUID = Field(
        ...,
        validation_alias="id",
        description="ID of the organization created",
    )
    orgSuperAdminEmail: Optional[EmailStr] = Field(None, description="Email of the auto-created org super admin")
    tempPassword: Optional[str] = Field(None, description="One-time password for the org super admin; shown only once")
