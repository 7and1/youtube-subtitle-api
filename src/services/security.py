"""
Security authentication and authorization functions.

SECURITY POLICY:
- Admin endpoints ALWAYS require authentication (fail closed)
- In development with no auth configured, a warning is logged and access is denied
- All security events are logged for audit purposes
"""

from __future__ import annotations

import hashlib
import hmac
import logging

import jwt
from fastapi import HTTPException, Request

from src.core.config import settings

logger = logging.getLogger(__name__)


def hash_ip_for_logs(ip: str) -> str:
    """Hash IP address for secure logging (GDPR/compliance friendly)."""
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()[:16]


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling X-Forwarded-For proxy headers."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def require_api_key(request: Request) -> None:
    """
    Require API key authentication.

    SECURITY: This now fails closed - if API_KEY is not configured,
    authentication will be denied with a clear error message.
    Uses constant-time comparison to prevent timing attacks.
    """
    if not settings.API_KEY:
        logger.error(
            "admin_auth_denied",
            extra={
                "reason": "API_KEY not configured",
                "client_ip": hash_ip_for_logs(get_client_ip(request)),
            },
        )
        raise HTTPException(
            status_code=500,
            detail="Server authentication not configured. Contact administrator.",
        )

    provided = request.headers.get(settings.API_KEY_HEADER_NAME, "")
    # SECURITY: Use hmac.compare_digest() for constant-time comparison to prevent
    # timing attacks. String comparison (==) returns early on first mismatch,
    # which leaks information about the correct prefix via timing side-channel.
    if not hmac.compare_digest(provided.encode("utf-8"), settings.API_KEY.encode("utf-8")):
        logger.warning(
            "admin_auth_failed",
            extra={
                "reason": "invalid_api_key",
                "client_ip": hash_ip_for_logs(get_client_ip(request)),
            },
        )
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    logger.info(
        "admin_auth_success",
        extra={
            "method": "api_key",
            "client_ip": hash_ip_for_logs(get_client_ip(request)),
        },
    )


def require_jwt(request: Request) -> None:
    """
    Require JWT authentication.

    SECURITY: This now fails closed - if JWT_SECRET is not configured,
    authentication will be denied with a clear error message.
    """
    if not settings.JWT_SECRET:
        logger.error(
            "admin_auth_denied",
            extra={
                "reason": "JWT_SECRET not configured",
                "client_ip": hash_ip_for_logs(get_client_ip(request)),
            },
        )
        raise HTTPException(
            status_code=500,
            detail="Server authentication not configured. Contact administrator.",
        )

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        logger.warning(
            "admin_auth_failed",
            extra={
                "reason": "missing_bearer_token",
                "client_ip": hash_ip_for_logs(get_client_ip(request)),
            },
        )
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = auth.removeprefix("Bearer ").strip()
    try:
        jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        logger.warning(
            "admin_auth_failed",
            extra={
                "reason": "token_expired",
                "client_ip": hash_ip_for_logs(get_client_ip(request)),
            },
        )
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        logger.warning(
            "admin_auth_failed",
            extra={
                "reason": "invalid_token",
                "client_ip": hash_ip_for_logs(get_client_ip(request)),
            },
        )
        raise HTTPException(status_code=401, detail="Invalid token")

    logger.info(
        "admin_auth_success",
        extra={
            "method": "jwt",
            "client_ip": hash_ip_for_logs(get_client_ip(request)),
        },
    )


def require_admin_auth(request: Request) -> None:
    """
    Admin authentication - FAILS CLOSED.

    Priority order:
    1. JWT authentication (when JWT_SECRET is configured)
    2. API key authentication (when API_KEY is configured)
    3. DENY ALL if neither is configured (security hardening)

    Environment variables:
    - JWT_SECRET: Set this to enable JWT bearer token auth
    - API_KEY: Set this to enable X-API-Key header auth

    SECURITY: This function now REQUIRES at least one auth method to be
    configured. In production, you must set either JWT_SECRET or API_KEY.
    """
    # Check for JWT first (more secure, supports expiration)
    if settings.JWT_SECRET:
        require_jwt(request)
        return

    # Fall back to API key
    if settings.API_KEY:
        require_api_key(request)
        return

    # SECURITY: Fail closed - no auth configured means no admin access
    client_ip = get_client_ip(request)
    hashed_ip = hash_ip_for_logs(client_ip)
    logger.error(
        "admin_auth_denied_no_config",
        extra={
            "reason": "no_auth_configured",
            "client_ip": hashed_ip,
            "environment": settings.ENVIRONMENT,
        },
    )
    raise HTTPException(
        status_code=500,
        detail=(
            "Server authentication not configured. "
            "Set either JWT_SECRET or API_KEY environment variable. "
            "Contact administrator."
        ),
    )
