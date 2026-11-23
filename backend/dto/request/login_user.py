from pydantic import BaseModel, EmailStr, Field


class LoginUserRequest(BaseModel):
    email: EmailStr = Field(..., description="Email address of the user")
    password: str = Field(..., description="Password of the user", min_length=1)
