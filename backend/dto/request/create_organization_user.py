from pydantic import BaseModel, EmailStr, Field, field_validator
from database.models.user import UserRole


class CreateOrganizationUserRequest(BaseModel):
    name: str = Field(..., description="Full name of the user", min_length=1)
    email: EmailStr = Field(..., description="Email address of the user")
    password: str = Field(..., description="Password of the user", min_length=8)
    role: UserRole = Field(UserRole.PARTICIPANT, description="Role of the user within the organization")

    @field_validator("role")
    @classmethod
    def role_within_org_scope(cls, v: UserRole) -> UserRole:
        if v not in (UserRole.PARTICIPANT, UserRole.ORG_ADMIN):
            raise ValueError("role must be participant or org_admin")
        return v
