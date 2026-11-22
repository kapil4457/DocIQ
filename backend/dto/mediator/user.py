from pydantic import BaseModel, Field, EmailStr
import uuid
from enum import Enum


class UserRole(str,Enum):
    PARTICIPANT = "participant"
    ADMIN = "admin"

class User(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Unique identifier for each user")
    name: str = Field(...,description="Full name of the user", min_length=1)
    email: EmailStr = Field(..., description="Email address of the user")
    password: str = Field(..., description="Password of the user")
    organizationId: uuid.UUID = Field(..., description="Organization to which the user belongs to")
    role: UserRole = Field(..., description="Role of the user")