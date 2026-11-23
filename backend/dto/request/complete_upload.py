from uuid import UUID
from pydantic import BaseModel, Field


class UploadedPart(BaseModel):
    partNumber: int = Field(..., ge=1, le=10000, description="1-based part number")
    etag: str = Field(..., min_length=1, description="ETag returned by storage for this part")


class CompleteUploadRequest(BaseModel):
    uploadId: str = Field(..., min_length=1, description="Multipart upload id returned at registration")
    parts: list[UploadedPart] = Field(..., min_length=1, description="ETags for each uploaded part")
    hash: str | None = Field(None, min_length=1, description="SHA-256 hex digest of the full file, computed by the uploading client")
