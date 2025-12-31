"""
YouTube Subtitle API - Main Entry Point

FastAPI service for extracting and caching YouTube subtitles.
Integrates with async task queue (RQ) for subtitle extraction.
"""

import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from fastapi.responses import Response
import anyio
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator

# Import routes and middleware
from src.api.routes import health, subtitles, admin
from src.api.middleware import (
    APIVersionMiddleware,
    RateLimitHeadersMiddleware,
    create_error_response,
    ErrorCodeException,
)
from src.core.config import settings
from src.core.logging_config import setup_logging
from src.services.cache import CacheManager
from src.services.database import DatabaseManager
from src.services.rate_limiter import RateLimiter
from src.services.in_memory_cache import InMemoryCache
from src.services.job_queue import QueueConfig, queue_stats
from src.services.subtitle_orchestrator import SubtitleOrchestrator
from src.metrics import job_queue_depth
from src.services.security import get_client_ip
from src.core.time_utils import utc_now

# Initialize logging
setup_logging(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


# Global state managers
cache_manager: Optional[CacheManager] = None
db_manager: Optional[DatabaseManager] = None
rate_limiter: Optional[RateLimiter] = None
memory_cache: Optional[InMemoryCache] = None
subtitle_orchestrator: Optional[SubtitleOrchestrator] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    Manages database connections, cache connections, and cleanup.
    """
    global cache_manager, db_manager, rate_limiter, memory_cache, subtitle_orchestrator

    # Startup
    logger.info("Initializing YouTube Subtitle API...")

    try:
        # Initialize services
        cache_manager = CacheManager(redis_url=settings.REDIS_URL)
        await cache_manager.connect()
        logger.info("Cache manager initialized")

        db_manager = DatabaseManager(
            database_url=settings.DATABASE_URL,
            db_schema=settings.DB_SCHEMA,
            pool_size=settings.DB_POOL_SIZE,
            pool_min_size=settings.DB_POOL_MIN_SIZE,
            pool_timeout=settings.DB_POOL_TIMEOUT,
            echo=settings.DB_ECHO,
        )
        await db_manager.connect()
        logger.info("Database manager initialized")

        # SECURITY: Rate limiter fails closed by default
        # Set RATE_LIMIT_FAIL_OPEN=true to allow requests when Redis is down
        rate_limiter = RateLimiter(
            redis_client=cache_manager.redis,
            requests_per_minute=settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
            burst_size=settings.RATE_LIMIT_BURST_SIZE,
            fail_open=settings.RATE_LIMIT_FAIL_OPEN,
        )
        logger.info(
            "Rate limiter initialized",
            extra={
                "fail_open": settings.RATE_LIMIT_FAIL_OPEN,
                "requests_per_minute": settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
            },
        )

        memory_cache = InMemoryCache(
            maxsize=int(os.getenv("MEMORY_CACHE_MAX_SIZE", "2000")),
            ttl_seconds=int(os.getenv("MEMORY_CACHE_TTL_SECONDS", "300")),
        )

        queue_cfg = QueueConfig(
            redis_url=settings.REDIS_URL,
            queue_name=settings.REDIS_QUEUE_NAME,
            default_timeout=settings.YT_EXTRACTION_TIMEOUT + 10,
            result_ttl=settings.REDIS_RESULT_TTL,
        )
        subtitle_orchestrator = SubtitleOrchestrator(
            memory_cache=memory_cache,
            cache_manager=cache_manager,
            db_manager=db_manager,
            queue_cfg=queue_cfg,
        )
        logger.info("Subtitle orchestrator initialized")

        # Initialize database schema (tables optional; prefer Alembic in production)
        await db_manager.init_schema(create_tables=settings.DB_AUTO_CREATE)
        logger.info("Database schema initialized")

        logger.info("YouTube Subtitle API started successfully")

    except Exception as e:
        logger.error(f"Startup failed: {e}", exc_info=True)
        raise

    yield

    # Shutdown
    logger.info("Shutting down YouTube Subtitle API...")
    try:
        await cache_manager.disconnect()
        await db_manager.disconnect()
        logger.info("Services shutdown completed")
    except Exception as e:
        logger.error(f"Shutdown error: {e}", exc_info=True)


# Create FastAPI application
app = FastAPI(
    title="YouTube Subtitle API",
    description="Extract and cache YouTube video subtitles with dual-engine extraction",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# Middleware: CORS
# SECURITY: ALLOWED_ORIGINS defaults to empty list (deny all).
# You MUST set ALLOWED_ORIGINS environment variable for cross-origin requests to work.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-Request-ID"],
    max_age=3600,  # 1 hour
    expose_headers=[
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "X-RateLimit-Policy",
        "X-Request-ID",
        "X-API-Version",
        "Retry-After",
    ],
)

# Middleware: Compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Middleware: API Versioning (enabled by default for backward compatibility)
if settings.API_DEPRECATED_PATH_REDIRECT:
    app.add_middleware(APIVersionMiddleware)

# Middleware: Rate Limit Headers
app.add_middleware(RateLimitHeadersMiddleware)


# Middleware: Request logging and rate limiting
@app.middleware("http")
async def request_logging_and_rate_limit(request: Request, call_next):
    """
    Middleware for request logging and rate limiting.
    - Logs request metadata
    - Enforces rate limiting per IP
    - Attaches context to state
    - Adds rate limit headers via request state
    """
    # Extract client IP (behind nginx-proxy)
    client_ip = get_client_ip(request)
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex

    # Attach managers to request state
    request.state.cache_manager = cache_manager
    request.state.db_manager = db_manager
    request.state.rate_limiter = rate_limiter
    request.state.memory_cache = memory_cache
    request.state.subtitle_orchestrator = subtitle_orchestrator
    request.state.client_ip = client_ip
    request.state.request_id = request_id

    # Rate limiting (skip health checks)
    rate_limit_info = None
    if request.url.path not in ["/health", "/live", "/metrics"]:
        # Some test transports don't execute lifespan hooks; fail open if uninitialized.
        if rate_limiter is not None:
            allowed, remaining, reset_at, info = await rate_limiter.check_rate_limit(
                client_ip, request.url.path
            )
            rate_limit_info = info
            # Store for header middleware
            request.state.rate_limit_info = {
                "limit": info.limit,
                "remaining": info.remaining,
                "reset_at": info.reset_at,
            }

            if not allowed:
                logger.warning(
                    f"Rate limit exceeded for {client_ip} on {request.url.path}",
                    extra={
                        "client_ip": client_ip,
                        "path": request.url.path,
                        "request_id": request_id,
                    },
                )
                retry_after = max(0, int((reset_at - utc_now()).total_seconds()))
                return create_error_response(
                    error_code="RATE_LIMIT_EXCEEDED",
                    request_id=request_id,
                    meta={"retry_after": retry_after, "reset_at": reset_at.isoformat()},
                )

    # Log request start
    start_time = utc_now()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-API-Version"] = settings.API_CURRENT_VERSION

    # Log request completion
    duration_ms = (utc_now() - start_time).total_seconds() * 1000
    logger.info(
        "Request completed",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "client_ip": client_ip,
            "request_id": request_id,
        },
    )

    return response


# Error handlers
@app.exception_handler(ErrorCodeException)
async def error_code_exception_handler(request: Request, exc: ErrorCodeException):
    """Custom ErrorCodeException handler with standardized error response."""
    request_id = getattr(request.state, "request_id", uuid.uuid4().hex)
    logger.warning(
        f"ErrorCodeException {exc.error_code}: {exc.detail}",
        extra={"path": request.url.path, "request_id": request_id},
    )
    return create_error_response(
        error_code=exc.error_code,
        status_code=exc.status_code,
        request_id=request_id,
        detail=exc.detail,
        meta=exc.meta,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler with standardized error response."""
    request_id = getattr(request.state, "request_id", uuid.uuid4().hex)

    # Map HTTP status codes to error codes
    error_code_map = {
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "SUBTITLE_NOT_FOUND",
        429: "RATE_LIMIT_EXCEEDED",
        500: "INTERNAL_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }

    error_code = error_code_map.get(exc.status_code, "INTERNAL_ERROR")
    logger.error(
        f"HTTP error {exc.status_code}: {exc.detail}",
        extra={"path": request.url.path, "request_id": request_id},
    )
    return create_error_response(
        error_code=error_code,
        status_code=exc.status_code,
        request_id=request_id,
        detail=str(exc.detail),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler for unhandled errors."""
    request_id = getattr(request.state, "request_id", uuid.uuid4().hex)
    logger.error(
        f"Unhandled exception: {exc}",
        exc_info=True,
        extra={"path": request.url.path, "request_id": request_id},
    )
    return create_error_response(
        error_code="INTERNAL_ERROR",
        request_id=request_id,
    )


# Include routes with v1 prefix
app.include_router(health.router, prefix="", tags=["Health"])
app.include_router(subtitles.router, prefix="/api/v1", tags=["Subtitles"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])

# Backward compatibility: include legacy routes (redirects handled by middleware)
app.include_router(subtitles.router, prefix="/api", tags=["Subtitles (Deprecated)"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin (Deprecated)"])

# Metrics
if settings.PROMETHEUS_ENABLED:
    Instrumentator().instrument(app)


@app.get("/metrics")
async def metrics():
    if settings.PROMETHEUS_ENABLED:
        # Keep queue depth fresh for scrapes.
        cfg = QueueConfig(
            redis_url=settings.REDIS_URL,
            queue_name=settings.REDIS_QUEUE_NAME,
            default_timeout=settings.YT_EXTRACTION_TIMEOUT + 10,
            result_ttl=settings.REDIS_RESULT_TTL,
        )
        stats = await anyio.to_thread.run_sync(lambda: queue_stats(cfg))
        job_queue_depth.set(stats.get("queue_depth", 0))
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    return Response(status_code=404)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    # Keep minimal to avoid shipping binary assets in this repo.
    return Response(status_code=204)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "YouTube Subtitle API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "status": "operational",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        workers=settings.WORKERS,
        reload=settings.ENVIRONMENT != "production",
        log_level=settings.LOG_LEVEL.lower(),
    )
