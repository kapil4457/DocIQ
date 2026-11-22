from pydantic import Field, HttpUrl
from database.models.base_model import Base
import uuid 
from enum import Enum
from typing import Optional


class MediaType(str,Enum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MD = "md"
    PNG = "png"
    HTML = "html"
    CSV = "csv"


class DocumentVersion(Base):
    versionId: uuid.UUID = Field(default_factory=uuid.uuid4, description="Version of the document that it represents")
    documentId: uuid.UUID = Field(..., description="Unique identifier for each document")
    sourceUrl: HttpUrl = Field(...,description="URL to access the actual document")
    mediaType: MediaType = Field(..., description="Media type of the document")
    workspaceId: Optional[uuid.UUID] = Field(default=None, description="Workspace under which it was uploaded")
    hash: str = Field(..., description="File hash value")
    
