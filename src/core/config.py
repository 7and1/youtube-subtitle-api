"""
Configuration management using Pydantic Settings.
Loads environment variables and provides type-safe access.

SECURITY: CORS defaults to an empty list (deny all). You must explicitly
configure ALLOWED_ORIGINS for your application to work.
"""

import json
import logging
from typing import Optional, List, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from functools import lru_cache

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # Service Configuration
    SERVICE_NAME: str = "youtube-subtitles-api"
    ENVIRONMENT: str = "development"  # development, staging, production
    LOG_LEVEL: str = "INFO"

    # API Server
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8010
    WORKERS: int = 2
    WORKER_TIMEOUT: int = 30

    # Database (PostgreSQL via Supabase)
    DATABASE_URL: str
    DB_SCHEMA: str = "youtube_subtitles"
    DB_POOL_SIZE: int = 10
    DB_POOL_MIN_SIZE: int = 2
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False  # SQL query logging
    DB_AUTO_CREATE: bool = (
        True  # Create tables automatically (dev/local). Prefer Alembic in production.
    )

    # Redis (Queue & Cache)
    REDIS_URL: str = "redis://localhost:6379/2"
    REDIS_QUEUE_NAME: str = "youtube-extraction"
    REDIS_RESULT_TTL: int = 86400  # 24 hours

    # YouTube Extraction Configuration
    YT_EXTRACTION_TIMEOUT: int = 30  # seconds
    YT_RETRY_MAX_ATTEMPTS: int = 3
    YT_RETRY_BACKOFF_FACTOR: float = 2.0
    YT_PROXY_URLS: Optional[str] = None  # Comma-separated proxy URLs
    YT_PROXY_AUTH: Optional[str] = None  # user:pass format
    PROXY_COOLDOWN_SECONDS: int = 60
    PROXY_MAX_FAILURES: int = 3

    # Monitoring & Observability
    PROMETHEUS_ENABLED: bool = True
    SENTRY_DSN: Optional[str] = None
    ENABLE_PROFILING: bool = False

    # Security
    JWT_SECRET: Optional[str] = None
    API_KEY: Optional[str] = None
    API_KEY_HEADER_NAME: str = "X-API-Key"

    # SECURITY: CORS configuration
    # Defaults to empty list (deny all) for security.
    # Set via environment variable ALLOWED_ORIGINS as comma-separated URLs.
    # Examples:
    #   ALLOWED_ORIGINS=https://example.com,https://www.example.com
    #   ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080
    # For development only, use "*" to allow all origins:
    #   ALLOWED_ORIGINS=*
    # Note: Using Optional[str] to avoid pydantic-settings JSON parsing issue
    # The validator will parse and return List[str]
    _allowed_origins_raw: Optional[str] = None
    ALLOWED_ORIGINS: List[str] = []

    # Rate Limiting (consolidated - removed duplicate section)
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 30
    RATE_LIMIT_BURST_SIZE: int = 5
    RATE_LIMIT_FAIL_OPEN: bool = False  # SECURITY: If False, deny requests when Redis is down
    CACHE_TTL_MINUTES: int = 1440  # 24 hours

    # API Versioning
    API_CURRENT_VERSION: str = "v1"
    API_DEPRECATED_VERSIONS: List[str] = []  # Versions that are deprecated but still supported
    API_DEPRECATED_PATH_REDIRECT: bool = True  # Enable auto-redirect from /api/ to /api/v1/

    # Worker Configuration
    WORKER_CONCURRENCY: int = 2
    WORKER_PREFETCH_MULTIPLIER: int = 1
    WORKER_DB_POOL_SIZE: int = 5

    # Webhook Configuration
    WEBHOOK_SECRET: Optional[str] = None  # Secret key for HMAC signature generation
    WEBHOOK_TIMEOUT: int = 10  # Webhook request timeout in seconds
    WEBHOOK_MAX_RETRIES: int = 3  # Maximum webhook delivery retry attempts

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _parse_allowed_origins(cls, v: Any, info) -> list[str]:
        """
        Parse ALLOWED_ORIGINS from environment variable.

        SECURITY: Default behavior is to return an empty list (deny all).
        This prevents accidental open CORS in production.

        To allow all origins (DANGEROUS, only for development):
        - Set ALLOWED_ORIGINS=* in environment

        To allow specific origins:
        - Set ALLOWED_ORIGINS=https://example.com,https://www.example.com
        """
        # Check _allowed_origins_raw first (workaround for pydantic-settings List parsing)
        raw_value = info.data.get("_allowed_origins_raw") if info.data else None
        if raw_value is not None:
            v = raw_value

        if v is None:
            # SECURITY: Default to empty list (deny all) instead of wildcard
            logger.warning(
                "cors_no_origins_configured",
                extra={
                    "message": "ALLOWED_ORIGINS not set. CORS will deny all requests. "
                              "Set ALLOWED_ORIGINS environment variable to allow specific origins."
                },
            )
            return []

        if isinstance(v, list):
            return [str(x) for x in v]

        if isinstance(v, str):
            s = v.strip()
            if not s:
                # Empty string means deny all
                return []

            if s == "*":
                # SECURITY: Log when wildcard is used
                logger.warning(
                    "cors_wildcard_enabled",
                    extra={
                        "message": "ALLOWED_ORIGINS='*' allows all origins. "
                                  "This is dangerous and should only be used in development."
                    },
                )
                return ["*"]

            if s.startswith("["):
                try:
                    parsed = json.loads(s)
                    if isinstance(parsed, list):
                        return [str(x) for x in parsed]
                except Exception:
                    pass

            # Comma-separated list of origins
            origins = [p.strip() for p in s.split(",") if p.strip()]
            logger.info(
                "cors_origins_configured",
                extra={"count": len(origins), "origins": origins[:5]},  # Log first 5 only
            )
            return origins

        return [str(v)]


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Caching ensures we read environment only once.
    """
    return Settings()


# Export settings
settings = get_settings()
