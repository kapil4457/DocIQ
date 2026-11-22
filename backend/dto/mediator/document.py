from pydantic import BaseModel, Field, HttpUrl
import uuid
from enum import Enum
from typing import Optional


class Scope(str,Enum):
    WORKSPACE = "workspace"
    GLOBAL = "global"

class Document(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Unique identifier for each document")
    workspaceId: Optional[uuid.UUID] = Field(default=None, description="Workspace under which it was uploaded")
    scope: Scope = Field(..., description="Scope of the current document.")
    organizationId: uuid.UUID = Field(..., description="Organization to which this document belongs to")
    documentName: str = Field(..., description="Original name of the source file")

