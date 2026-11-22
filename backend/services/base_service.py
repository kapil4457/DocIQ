import time
from typing import Callable
from pydantic import BaseModel
from sqlalchemy import text
from database.db_engine import engine
import logging

logger = logging.getLogger("app.services.health")


class CheckResult(BaseModel):
    healthy: bool
    latency_ms: float
    detail: str | None = None


HealthCheckFn = Callable[[], tuple[bool, str | None]]
_CHECKS: dict[str, HealthCheckFn] = {}


def register_health_check(name: str):
    """Decorator to register a new dependency health check."""
    def decorator(fn: HealthCheckFn) -> HealthCheckFn:
        _CHECKS[name] = fn
        return fn
    return decorator


def run_all_health_checks() -> tuple[bool, dict[str, CheckResult]]:
    results: dict[str, CheckResult] = {}
    all_healthy = True

    for name, check_fn in _CHECKS.items():
        start = time.perf_counter()
        try:
            is_ok, detail = check_fn()
        except Exception as exc:
            is_ok, detail = False, str(exc)

        latency = round((time.perf_counter() - start) * 1000, 2)
        results[name] = CheckResult(healthy=is_ok, latency_ms=latency, detail=detail)
        if not is_ok:
            logger.error(
                f"Health check '{name}' failed",
                extra={"extra_data": {"check": name, "detail": detail, "latency_ms": latency}},
            )
            all_healthy = False

    return all_healthy, results


# --- Register individual checks below (or in their own modules) ---

@register_health_check("database")
def check_database() -> tuple[bool, str | None]:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True, "connected"


@register_health_check("pgvector")
def check_pgvector() -> tuple[bool, str | None]:
    with engine.connect() as conn:
        ext = conn.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        ).scalar()
    return (True, "enabled") if ext else (False, "vector extension missing")
