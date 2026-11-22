from pydantic import BaseModel, Field, EmailStr

class CreateOrganizationResponse(BaseModel):
    name: str = Field(...,description="Name of the organization", min_length=1)
    supportEmail: EmailStr = Field(..., description="Support email address of the organization")