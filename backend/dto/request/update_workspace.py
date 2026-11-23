from typing import Optional
from pydantic import BaseModel, Field


class UpdateWorkspaceRequest(BaseModel):
    name: Optional[str] = Field(None, description="New name for the workspace", min_length=1, max_length=255)
