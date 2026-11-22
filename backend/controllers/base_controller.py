from fastapi import APIRouter, status, Response
from services.base_service import run_all_health_checks


router = APIRouter(tags=["Health"])


@router.get("/", status_code=status.HTTP_200_OK)
async def root():
    return {
        "service": "DocIQ API",
        "status": "running",
        "docs": "/docs",
    }


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check(response: Response):
    is_healthy, checks = run_all_health_checks()
    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "checks": checks,
    }
