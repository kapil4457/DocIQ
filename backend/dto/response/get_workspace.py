from uuid import UUID
from pydantic import BaseModel, Field


class GetWorkspaceResponse(BaseModel):
    id: UUID = Field(..., description="ID of the workspace")
    name: str = Field(..., description="Name of the workspace")
    creatorId: UUID = Field(..., description="User who created the workspace")
    memberCount: int = Field(0, description="Number of members")
    message: str = Field(default="", description="Response message")
