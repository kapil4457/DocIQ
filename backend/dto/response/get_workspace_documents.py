from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field


class WorkspaceDocumentVersion(BaseModel):
    versionId: UUID = Field(..., description="ID of the version")
    status: str = Field(..., description="pending, available or aborted")
    isActive: bool = Field(False, description="True for the most recent available version")
    uploadedByName: Optional[str] = Field(None, description="Name of the uploader")
    fileSize: Optional[int] = Field(None, description="Size in bytes")
    createdAt: datetime = Field(..., description="Upload timestamp")
    quarantineReason: Optional[str] = Field(None, description="Failure reason when status is security_failed, quarantined or processing_failed")


class WorkspaceDocumentRow(BaseModel):
    documentId: UUID = Field(..., description="ID of the document trail")
    name: str = Field(..., description="Document name")
    uploadedByName: Optional[str] = Field(None, description="Name of the original uploader")
    createdAt: datetime = Field(..., description="When the document was first added")
    versionCount: int = Field(..., description="Number of versions in the trail")
    mediaTypes: list[str] = Field(default_factory=list, description="Distinct media types across versions")
    versions: list[WorkspaceDocumentVersion] = Field(..., description="Full version trail, newest first")


class GetWorkspaceDocumentsResponse(BaseModel):
    documents: list[WorkspaceDocumentRow] = Field(..., description="Page of documents")
    total: int = Field(..., description="Total documents in the workspace")
    page: int = Field(...)
    pageSize: int = Field(...)
    message: str = Field(default="")
