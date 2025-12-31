"""
Health check endpoints.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.core.time_utils import utc_now_iso_z

router = APIRouter()


@router.get(
    "/health",
    summary="Health check",
    operation_id="health_check",
    responses={
        200: {"description": "Service is healthy"},
        503: {"description": "Service is degraded"},
    },
)
async def health_check(request: Request):
    """
    Health check endpoint for load balancers and Kubernetes.

    Returns service and dependency health status. Returns 200 when all
    components are healthy, 503 when any component is degraded.
    """
    cache_manager = request.state.cache_manager
    db_manager = request.state.db_manager

    # Check dependencies
    redis_status = "connected"
    try:
        await cache_manager.redis.ping()
    except Exception:
        redis_status = "disconnected"

    postgres_status = "connected"
    try:
        await db_manager.health_check()
    except Exception:
        postgres_status = "disconnected"

    # Overall status
    healthy = redis_status == "connected" and postgres_status == "connected"
    status_code = 200 if healthy else 503

    payload = {
        "status": "healthy" if healthy else "degraded",
        "timestamp": utc_now_iso_z(),
        "api_version": settings.API_CURRENT_VERSION,
        "components": {
            "api": "ready",
            "redis": redis_status,
            "postgres": postgres_status,
        },
    }

    # Include Tier-1 cache stats if present
    try:
        mem = request.state.memory_cache
        payload["memory_cache"] = {
            "size": await mem.size(),
            "hit_rate": round(mem.stats.hit_rate, 4),
            "hits": mem.stats.hits,
            "misses": mem.stats.misses,
        }
    except Exception:
        pass

    response = JSONResponse(status_code=status_code, content=payload)
    # Health endpoints also get API version header
    response.headers["X-API-Version"] = settings.API_CURRENT_VERSION
    return response


@router.get(
    "/status",
    summary="Service status",
    operation_id="service_status",
)
async def service_status(request: Request):
    """Get detailed service status including version and environment."""
    return {
        "service": settings.SERVICE_NAME,
        "version": "1.0.0",
        "api_version": settings.API_CURRENT_VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": utc_now_iso_z(),
    }


@router.get(
    "/live",
    summary="Liveness probe",
    operation_id="liveness",
)
async def liveness():
    """
    Liveness probe for Kubernetes.

    Returns immediately if the process is running. Use this for
    quick liveness checks - it does not check external dependencies.
    """
    return {"status": "ok"}
