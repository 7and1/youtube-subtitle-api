"""
YouTube Subtitle API - FastAPI Application
Dual-engine subtitle extraction with VTT cleaning for AI consumption.
"""
import os
import re
import time
import hashlib
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from cachetools import TTLCache
import structlog

from app.services.subtitle_service import SubtitleService, SubtitleResult

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Configuration from environment
API_KEY = os.getenv("API_KEY", "")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", "5"))
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
CACHE_MAX_SIZE = int(os.getenv("CACHE_MAX_SIZE", "500"))

# In-memory caches
subtitle_cache: TTLCache = TTLCache(maxsize=CACHE_MAX_SIZE, ttl=CACHE_TTL_SECONDS)
rate_limit_cache: TTLCache = TTLCache(maxsize=10000, ttl=60)

# Concurrency tracking
current_requests = 0

# Subtitle service instance
subtitle_service: Optional[SubtitleService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global subtitle_service
    subtitle_service = SubtitleService()
    logger.info("youtube_subtitle_api_started",
                cache_ttl=CACHE_TTL_SECONDS,
                rate_limit=RATE_LIMIT_PER_MINUTE)
    yield
    logger.info("youtube_subtitle_api_stopped")


app = FastAPI(
    title="YouTube Subtitle API",
    description="Extract and clean YouTube subtitles for AI consumption",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# Request/Response Models
class SubtitleRequest(BaseModel):
    """Request model for subtitle extraction."""
    video_id: Optional[str] = Field(None, description="YouTube video ID (11 characters)")
    url: Optional[str] = Field(None, description="YouTube video URL")
    language: str = Field(default="en", description="Preferred subtitle language")
    clean_for_ai: bool = Field(default=True, description="Clean VTT formatting for AI")

    @field_validator("video_id")
    @classmethod
    def validate_video_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        pattern = r"^[a-zA-Z0-9_-]{11}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid video ID format. Must be 11 alphanumeric characters.")
        return v

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        valid_domains = ["youtube.com", "youtu.be", "youtube-nocookie.com", "www.youtube.com"]
        if not any(domain in v for domain in valid_domains):
            raise ValueError("URL must be from youtube.com or youtu.be")
        return v


class SubtitleResponse(BaseModel):
    """Response model for subtitle extraction."""
    success: bool
    video_id: str
    title: Optional[str] = None
    language: str
    extraction_method: str
    subtitle_count: int
    duration_ms: int
    cached: bool
    subtitles: list[dict]
    plain_text: Optional[str] = None
    proxy_used: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    cache_size: int
    cache_hit_rate: float
    uptime_seconds: int
    proxy_stats: Optional[dict] = None


# Track startup time for uptime calculation
startup_time = time.time()
cache_hits = 0
cache_misses = 0


def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(client_ip: str) -> bool:
    """Check if client is within rate limit."""
    # Hash IP for privacy
    ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:16]
    current_count = rate_limit_cache.get(ip_hash, 0)

    if current_count >= RATE_LIMIT_PER_MINUTE:
        return False

    rate_limit_cache[ip_hash] = current_count + 1
    return True


def verify_api_key(request: Request) -> bool:
    """Verify API key from header."""
    if not API_KEY:
        return True  # No API key configured = open access

    provided_key = request.headers.get("X-API-Key", "")
    return provided_key == API_KEY


def extract_video_id(url: str) -> Optional[str]:
    """Extract video ID from YouTube URL."""
    patterns = [
        r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:embed/)([a-zA-Z0-9_-]{11})",
        r"(?:shorts/)([a-zA-Z0-9_-]{11})"
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    global cache_hits, cache_misses
    total = cache_hits + cache_misses
    hit_rate = cache_hits / total if total > 0 else 0.0

    # Get proxy stats if available
    proxy_stats = None
    if subtitle_service:
        proxy_stats = subtitle_service.get_proxy_stats()

    return HealthResponse(
        status="healthy",
        cache_size=len(subtitle_cache),
        cache_hit_rate=round(hit_rate, 2),
        uptime_seconds=int(time.time() - startup_time),
        proxy_stats=proxy_stats
    )


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "service": "YouTube Subtitle API",
        "version": "1.0.0",
        "endpoints": {
            "health": "GET /health",
            "extract": "POST /api/subtitles",
            "docs": "GET /docs"
        }
    }


@app.post("/api/subtitles", response_model=SubtitleResponse)
async def extract_subtitles(request: Request, body: SubtitleRequest):
    """
    Extract subtitles from a YouTube video.

    Dual-engine approach:
    1. First tries youtube-transcript-api (fast, reliable)
    2. Falls back to yt-dlp if primary fails
    """
    global current_requests, cache_hits, cache_misses

    # Verify API key
    if not verify_api_key(request):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    # Rate limiting
    client_ip = get_client_ip(request)
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {RATE_LIMIT_PER_MINUTE} requests per minute."
        )

    # Concurrency check
    if current_requests >= MAX_CONCURRENT:
        raise HTTPException(
            status_code=503,
            detail="Service busy. Please retry in a few seconds."
        )

    # Resolve video ID
    video_id = body.video_id
    if not video_id and body.url:
        video_id = extract_video_id(body.url)

    if not video_id:
        raise HTTPException(
            status_code=400,
            detail="Must provide either video_id or url"
        )

    # Check cache
    cache_key = f"{video_id}:{body.language}"
    if cache_key in subtitle_cache:
        cache_hits += 1
        cached_result = subtitle_cache[cache_key]
        logger.info("cache_hit", video_id=video_id, language=body.language)
        return SubtitleResponse(
            success=True,
            video_id=video_id,
            title=cached_result.get("title"),
            language=body.language,
            extraction_method=cached_result.get("method", "cached"),
            subtitle_count=len(cached_result.get("subtitles", [])),
            duration_ms=0,
            cached=True,
            subtitles=cached_result.get("subtitles", []),
            plain_text=cached_result.get("plain_text")
        )

    cache_misses += 1

    # Extract subtitles
    current_requests += 1
    start_time = time.time()

    try:
        result: SubtitleResult = await subtitle_service.extract(
            video_id=video_id,
            language=body.language,
            clean_for_ai=body.clean_for_ai
        )

        duration_ms = int((time.time() - start_time) * 1000)

        if not result.success:
            logger.warning("extraction_failed",
                          video_id=video_id,
                          error=result.error,
                          duration_ms=duration_ms)
            raise HTTPException(status_code=404, detail=result.error)

        # Cache the result
        subtitle_cache[cache_key] = {
            "title": result.title,
            "subtitles": result.subtitles,
            "plain_text": result.plain_text,
            "method": result.extraction_method
        }

        logger.info("extraction_success",
                   video_id=video_id,
                   method=result.extraction_method,
                   subtitle_count=len(result.subtitles),
                   duration_ms=duration_ms)

        return SubtitleResponse(
            success=True,
            video_id=video_id,
            title=result.title,
            language=body.language,
            extraction_method=result.extraction_method,
            subtitle_count=len(result.subtitles),
            duration_ms=duration_ms,
            cached=False,
            subtitles=result.subtitles,
            plain_text=result.plain_text,
            proxy_used=result.proxy_used
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("extraction_error", video_id=video_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")

    finally:
        current_requests -= 1


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error("unhandled_exception",
                path=request.url.path,
                error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )
