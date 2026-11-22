from pydantic import BaseModel, Field
from http import HTTPStatus


class BaseResponse(BaseModel):
    message: str = Field(default="", description="Response message")
    code: HTTPStatus = Field(default=HTTPStatus.OK , description="Response code")