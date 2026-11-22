from pydantic import BaseModel, Field
import uuid

class Workspace(BaseModel):
    id: uuid.UUID = Field(description="Unique identifier for each workspace",default_factory=uuid.uuid4)
    name: str = Field(...,description="Name of the workspace", min_length=1)
    userId: uuid.UUID = Field(..., description="User who created this workspace")

