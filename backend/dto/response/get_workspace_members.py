from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field


class WorkspaceUser(BaseModel):
    id: UUID = Field(..., description="User id")
    name: str = Field(...)
    email: str = Field(...)
    role: str = Field(..., description="Organization role of the member")
    isCreator: bool = Field(False, description="Whether this member created the workspace")


class GetWorkspaceMembersResponse(BaseModel):
    members: list[WorkspaceUser] = Field(...)
    total: int = Field(...)
    message: str = Field(default="")
