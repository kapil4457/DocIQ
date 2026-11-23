from uuid import UUID
from pydantic import ConfigDict, Field
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
