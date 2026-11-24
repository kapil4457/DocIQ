from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field
from database.models.document import Scope
from database.models.document_version import MediaType

MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB


class RegisterDocumentRequest(BaseModel):
    workspaceId: Optional[UUID] = Field(None, description="Workspace under which it was uploaded")
    documentId: Optional[UUID] = Field(None, description="Parent document under which it is being uploaded")
    scope: Scope = Field(..., description="Scope of the document")
    organizationId: Optional[UUID] = Field(None, description="Organization to which this document belongs; derived from the workspace when workspace-scoped")
    documentName: str = Field(..., description="Original name of the source file", min_length=1)
    mediaType: MediaType = Field(..., description="Media type of the source file")
    fileSize: int = Field(..., gt=0, le=MAX_FILE_SIZE, description="Size of the file in bytes (max 500 MB)")
