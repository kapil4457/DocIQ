from uuid import UUID
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from database.models.user import UserRole


class CreateUserRequest(BaseModel):
    name: str = Field(..., description="Full name of the user", min_length=1)
    email: EmailStr = Field(..., description="Email address of the user")
    password: str = Field(..., description="Password of the user", min_length=8)
    organizationId: Optional[UUID] = Field(None, description="Organization to which the user belongs")
    role: UserRole = Field(..., description="Role of the user")
