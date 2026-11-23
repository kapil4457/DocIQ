from uuid import UUID
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from dto.response.base_response import BaseResponse
from database.models.document import Scope
from database.models.document_version import DocumentVersionStatus


class CompleteUploadResponse(BaseResponse):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    documentId: UUID = Field(..., description="ID of the document")
    versionId: UUID = Field(..., description="ID of the completed document version")
    status: DocumentVersionStatus = Field(..., description="Status of the document version")
    sourceUrl: str = Field(..., description="URL where the document is available")
    fileSize: int = Field(..., description="Size of the stored object in bytes")
    etag: str = Field(..., description="ETag of the stored object")
    hash: Optional[str] = Field(None, description="SHA-256 content hash when the client supplied one, otherwise the storage ETag")
    workspaceId: Optional[UUID] = Field(None, description="Workspace under which it was uploaded")
    organizationId: UUID = Field(..., description="Organization to which this document belongs")
    documentName: str = Field(..., description="Name of the document")
    mediaType: str = Field(..., description="Media type of the document")
    createdAt: datetime = Field(..., description="Timestamp of creation")
