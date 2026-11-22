from pydantic import BaseModel, Field
from uuid import UUID,uuid4
from typing import Optional

class DocumentEmbeddingMetaData(BaseModel):
    tags: list[str] = Field(default_factory=list, description="Custom tags for metadata filtering")
    chunkIndex: int = Field(..., description="0-based sequence index of the chunk")
    pageNumber: Optional[int] = Field(None, description="Page number if applicable")
    sectionTitle: Optional[str] = Field(None, description="Nearest parent heading")
    embeddingModel: str = Field(..., description="Model used to generate the vector")

class DocumentEmbedding(BaseModel):
    documentEmbeddingId: UUID = Field(default_factory=uuid4, description="Unique identifier for the document embedding")
    documentId: UUID = Field(..., description="Source document that this embedding belongs to")
    content: str = Field(..., description="Raw chunk content for this embedding")
    embedding: list[float] = Field(..., description="Embedding for the raw content")
    metadata: DocumentEmbeddingMetaData = Field(..., description="Metadata linked to the embedding used for filtering.")

