from pydantic import BaseModel, EmailStr, Field, field_validator
from database.models.user import UserRole


class CreateOrganizationUserRequest(BaseModel):
    name: str = Field(..., description="Full name of the user", min_length=1)
    email: EmailStr = Field(..., description="Email address of the user")
    password: str = Field(..., description="Password of the user", min_length=8)
    role: UserRole = Field(UserRole.PARTICIPANT, description="Role of the user within the organization")

    @field_validator("role")
    @classmethod
    def role_not_super_admin(cls, v: UserRole) -> UserRole:
        if v == UserRole.SUPER_ADMIN:
            raise ValueError("super_admin users cannot be created through an organization")
        return v
