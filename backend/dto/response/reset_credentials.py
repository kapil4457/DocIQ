from pydantic import BaseModel, EmailStr, Field


class ResetCredentialsResponse(BaseModel):
    email: EmailStr = Field(..., description="Email of the user whose credentials were reset")
    temporaryPassword: str = Field(..., description="One-time temporary password; shown only once")
    message: str = Field(default="Credentials reset successfully")
