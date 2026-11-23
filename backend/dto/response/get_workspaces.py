from uuid import UUID
from pydantic import BaseModel, Field


class WorkspaceResponse(BaseModel):
    id: UUID = Field(..., description="ID of the workspace")
    name: str = Field(..., description="Name of the workspace")
    creatorId: UUID = Field(..., description="User who created the workspace")
    memberCount: int = Field(0, description="Number of members")


class GetAllWorkspacesResponse(BaseModel):
    workspaces: list[WorkspaceResponse] = Field(..., description="Page of workspaces")
    total: int = Field(..., description="Total workspaces accessible to the user")
    page: int = Field(...)
    pageSize: int = Field(...)
    message: str = Field(default="", description="Response message")
