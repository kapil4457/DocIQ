from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class UpdateOrganizationRequest(BaseModel):
    name: Optional[str] = Field(None, description="Name of the organization", min_length=1)
    supportEmail: Optional[EmailStr] = Field(None, description="Support email address of the organization")
