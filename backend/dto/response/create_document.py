from uuid import UUID
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from dto.response.base_response import BaseResponse
from database.models.document import Scope


class PresignedPartUrl(BaseModel):
    partNumber: int = Field(..., description="1-based part number")
    url: str = Field(..., description="Presigned URL for uploading this part")


class UploadInfo(BaseModel):
    uploadId: str = Field(..., description="Multipart upload id")
    objectKey: str = Field(..., description="Object key for this document version")
    chunkSize: int = Field(..., description="Part size in megabytes")
    partUrls: list[PresignedPartUrl] = Field(..., description="Presigned URLs for each part")


class RegisterDocumentResponse(BaseResponse):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    documentId: UUID = Field(
        ...,
        validation_alias="id",
        description="ID of the document",
    )
    versionId: UUID = Field(..., description="ID of the created document version")
    workspaceId: Optional[UUID] = Field(None, description="Workspace under which it was uploaded")
    scope: Scope = Field(..., description="Scope of the document")
    organizationId: UUID = Field(..., description="Organization to which this document belongs")
    documentName: str = Field(..., description="Name of the document")
    upload: UploadInfo = Field(..., description="Presigned multipart upload details")
