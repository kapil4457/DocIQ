from pydantic import BaseModel, EmailStr, Field


class AddWorkspaceMemberRequest(BaseModel):
    email: EmailStr = Field(..., description="Email of the organization user to add to the workspace")
