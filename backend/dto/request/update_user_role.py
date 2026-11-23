from pydantic import BaseModel, Field, field_validator
from database.models.user import UserRole


class UpdateUserRoleRequest(BaseModel):
    role: UserRole = Field(..., description="New role for the user")

    @field_validator("role")
    @classmethod
    def role_within_org_scope(cls, v: UserRole) -> UserRole:
        if v not in (UserRole.PARTICIPANT, UserRole.ORG_ADMIN):
            raise ValueError("role can only be toggled between participant and org_admin")
        return v
