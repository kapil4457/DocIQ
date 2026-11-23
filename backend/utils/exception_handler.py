from fastapi.responses import JSONResponse
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
import json


class AppError(Exception):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "An unexpected error occurred."

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.default_detail
        super().__init__(self.detail)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Resource not found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Resource state conflict"


class ObjectStorageError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "Failed to initialize file upload"


async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "ValidationError",
                "detail": exc.errors(),
            },
        )

    status_code = getattr(exc, "status_code", 500)
    detail = getattr(exc, "detail", str(exc) or "An unexpected error occurred.")

    try:
        body = await request.json()
    except json.JSONDecodeError:
        raw_body = await request.body()
        body = raw_body.decode("utf-8", errors="replace") if raw_body else None
    except Exception:
        body = None

    return JSONResponse(
        status_code=status_code,
        content={
            "error": type(exc).__name__,
            "detail": detail,
            "request_body": body,
        }
    )
