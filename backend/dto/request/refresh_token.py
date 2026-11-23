from pydantic import BaseModel, Field


class RefreshTokenRequest(BaseModel):
    refreshToken: str = Field(..., description="Refresh token issued at login", min_length=1)
