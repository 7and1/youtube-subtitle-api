"""
API middleware for versioning, headers, and error handling.
"""

import logging
import time
import uuid
from typing import Any, Optional

from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match

from src.core.config import settings
from src.core.time_utils import utc_now

logger = logging.getLogger(__name__)


# Standard error codes and messages
ERROR_CODES = {
    "RATE_LIMIT_EXCEEDED": {
        "message": "Rate limit exceeded",
        "hint": "Wait before making another request or upgrade your API plan",
        "status": 429,
    },
    "INVALID_VIDEO_ID": {
        "message": "Invalid YouTube video ID or URL format",
        "hint": "Provide a valid 11-character video ID or full YouTube URL",
        "status": 400,
    },
    "SUBTITLE_NOT_FOUND": {
        "message": "Subtitles not found or not yet extracted",
        "hint": "The video may not have subtitles in the requested language, or extraction is still pending",
        "status": 404,
    },
    "UNAUTHORIZED": {
        "message": "Authentication required",
        "hint": "Provide a valid API key via X-API-Key header",
        "status": 401,
    },
    "FORBIDDEN": {
        "message": "Access forbidden",
        "hint": "You do not have permission to access this resource",
        "status": 403,
    },
    "INTERNAL_ERROR": {
        "message": "Internal server error",
        "hint": "An unexpected error occurred. Please try again later",
        "status": 500,
    },
    "SERVICE_UNAVAILABLE": {
        "message": "Service temporarily unavailable",
        "hint": "The service is experiencing issues. Please try again later",
        "status": 503,
    },
    "INVALID_REQUEST": {
        "message": "Invalid request format",
        "hint": "Check your request parameters and try again",
        "status": 400,
    },
}


class APIVersionMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle API versioning and backward compatibility.
    Redirects /api/* to /api/v1/* with deprecation warning.
    """

    async def dispatch(self, request: Request, call_next):
        # Only process API routes
        if request.url.path.startswith("/api/") and not request.url.path.startswith(
            "/api/v1/"
        ):
            # Check if this is a direct /api/ call (not /api/v1/)
            if request.url.path.startswith("/api/admin"):
                # Admin routes go through /api/v1/admin/
                new_path = request.url.path.replace("/api/admin", "/api/v1/admin", 1)
            else:
                # Subtitle routes go through /api/v1/subtitles
                new_path = request.url.path.replace("/api/", "/api/v1/", 1)

            # Return redirect with deprecation warning
            response = JSONResponse(
                status_code=308,  # Permanent redirect
                content={
                    "redirect": new_path,
                    "warning": "API path deprecated. Use /api/v1/ prefix instead.",
                },
                headers={
                    "Location": new_path,
                    "X-API-Deprecation": "true",
                    "X-API-Version": "v1",
                },
            )
            return response

        response = await call_next(request)
        return response


class RateLimitHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add rate limit headers to all responses.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Skip rate limit headers for health/metrics endpoints
        if request.url.path in ["/health", "/live", "/metrics", "/favicon.ico"]:
            return response

        # Get rate limit info from request state (populated by rate limiter)
        rate_limit_info = getattr(request.state, "rate_limit_info", None)

        if rate_limit_info:
            response.headers["X-RateLimit-Limit"] = str(
                rate_limit_info.get("limit", settings.RATE_LIMIT_REQUESTS_PER_MINUTE)
            )
            response.headers["X-RateLimit-Remaining"] = str(
                rate_limit_info.get("remaining", settings.RATE_LIMIT_REQUESTS_PER_MINUTE)
            )
            response.headers["X-RateLimit-Reset"] = str(
                int(rate_limit_info.get("reset_at", time.time() + 60))
            )
            response.headers["X-RateLimit-Policy"] = (
                f"{settings.RATE_LIMIT_REQUESTS_PER_MINUTE};w=60;burst={settings.RATE_LIMIT_BURST_SIZE}"
            )
        else:
            # Default headers when rate limiting is not applied
            response.headers["X-RateLimit-Limit"] = str(
                settings.RATE_LIMIT_REQUESTS_PER_MINUTE
            )
            response.headers["X-RateLimit-Remaining"] = str(
                settings.RATE_LIMIT_REQUESTS_PER_MINUTE
            )
            response.headers["X-RateLimit-Reset"] = str(int(time.time() + 60))
            response.headers["X-RateLimit-Policy"] = (
                f"{settings.RATE_LIMIT_REQUESTS_PER_MINUTE};w=60;burst={settings.RATE_LIMIT_BURST_SIZE}"
            )

        return response


def create_error_response(
    error_code: str,
    status_code: Optional[int] = None,
    request_id: Optional[str] = None,
    detail: Optional[str] = None,
    meta: Optional[dict[str, Any]] = None,
) -> JSONResponse:
    """
    Create a standardized error response.

    Args:
        error_code: Error code key from ERROR_CODES
        status_code: HTTP status code (defaults to error's status)
        request_id: Request ID for tracing
        detail: Additional error details
        meta: Additional metadata to include

    Returns:
        JSONResponse with standardized error format
    """
    error_info = ERROR_CODES.get(error_code, ERROR_CODES["INTERNAL_ERROR"])

    content = {
        "error": {
            "code": error_code,
            "message": detail or error_info["message"],
        }
    }

    # Add hint if available
    if error_info.get("hint"):
        content["error"]["hint"] = error_info["hint"]

    # Add request ID for debugging
    if request_id:
        content["error"]["request_id"] = request_id

    # Add additional metadata
    if meta:
        content["error"]["meta"] = meta

    # Add timestamp
    content["error"]["timestamp"] = utc_now().isoformat()

    return JSONResponse(
        status_code=status_code or error_info["status"],
        content=content,
        headers={
            "Content-Type": "application/problem+json",
            "X-Error-Code": error_code,
        },
    )


class ErrorCodeException(HTTPException):
    """
    HTTP exception with error code support.
    """

    def __init__(
        self,
        error_code: str,
        status_code: Optional[int] = None,
        detail: Optional[str] = None,
        meta: Optional[dict[str, Any]] = None,
    ):
        self.error_code = error_code
        self.meta = meta
        error_info = ERROR_CODES.get(error_code, ERROR_CODES["INTERNAL_ERROR"])
        super().__init__(
            status_code=status_code or error_info["status"],
            detail=detail or error_info["message"],
        )
