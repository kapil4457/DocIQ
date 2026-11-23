from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., description="Name of the workspace", min_length=1, max_length=255)
