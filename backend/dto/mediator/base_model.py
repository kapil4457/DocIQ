from datetime import datetime
from pydantic import Field
from uuid import UUID
from pydantic import BaseModel

class Base(BaseModel):
    createdAt: datetime = Field(..., description="Timestamp of creation")
    createdBy: UUID = Field(..., description="User id of the creator")
    modifiedAt: datetime = Field(..., description="Timestamp of last modification")
    modifiedBy: UUID = Field(..., description="User id of the modifier")