"""
Subtitle extraction endpoints.
"""

import logging
import re
from typing import Optional, Any
from urllib.parse import urlparse

from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, AliasChoices, ConfigDict, HttpUrl

from src.api.middleware import ErrorCodeException

logger = logging.getLogger(__name__)

router = APIRouter()

# URL validation patterns
YOUTUBE_URL_PATTERN = r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=|shorts\/)?([a-zA-Z0-9_-]{11})"
VIDEO_ID_PATTERN = r"^[a-zA-Z0-9_-]{11}$"


class SubtitleRequest(BaseModel):
    """Request model for subtitle extraction."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "language": "en",
                "clean_for_ai": True,
                "webhook_url": "https://example.com/webhook",
            }
        }
    )

    video_url: Optional[str] = Field(
        default=None,
        description="YouTube URL",
        validation_alias=AliasChoices("video_url", "url"),
    )
    video_id: Optional[str] = Field(
        default=None, description="YouTube video ID (11 chars)"
    )
    language: str = Field(default="en", description="Preferred language")
    clean_for_ai: bool = Field(
        default=True, description="Normalize/clean text for AI consumption"
    )
    webhook_url: Optional[str] = Field(
        default=None,
        description="Optional webhook URL to receive job completion notification",
    )

    @field_validator("video_id")
    @classmethod
    def validate_video_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not re.match(VIDEO_ID_PATTERN, v):
            raise ValueError("Invalid video ID format")
        return v

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        # Validate webhook URL format
        try:
            parsed = urlparse(v)
            if not parsed.scheme or parsed.scheme not in ("http", "https"):
                raise ValueError("Webhook URL must use http or https scheme")
            if not parsed.netloc:
                raise ValueError("Webhook URL must have a valid host")
        except Exception as e:
            raise ValueError(f"Invalid webhook URL: {e}")
        return v


class ExtractionQueuedResponse(BaseModel):
    job_id: str
    status: str = "queued"
    video_id: str
    language: str
    webhook_url: Optional[str] = None


async def _extract_or_enqueue(
    request: Request, subtitle_req: SubtitleRequest
):
    """
    Extract and return subtitles for a YouTube video.

    Dual-engine extraction:
    1. youtube-transcript-api (fast, cached transcripts)
    2. yt-dlp fallback (handles restricted videos)

    Rate limited per IP: 30 requests/minute
    """
    from src.services.security import require_api_key_if_configured, hash_ip_for_logs

    require_api_key_if_configured(request)
    orchestrator = request.state.subtitle_orchestrator

    try:
        # Extract video ID
        video_id = subtitle_req.video_id
        if not video_id and subtitle_req.video_url:
            match = re.search(YOUTUBE_URL_PATTERN, subtitle_req.video_url)
            if match:
                video_id = match.group(1)

        if not video_id or not re.match(VIDEO_ID_PATTERN, video_id):
            raise ErrorCodeException(
                error_code="INVALID_VIDEO_ID",
                detail="Invalid video ID or URL format. Provide a valid 11-character YouTube video ID.",
            )

        cached = await orchestrator.get_cached(
            video_id=video_id, language=subtitle_req.language
        )
        if cached:
            return cached

        job_id = await orchestrator.enqueue_extraction(
            video_id=video_id,
            language=subtitle_req.language,
            clean_for_ai=subtitle_req.clean_for_ai,
            client_ip_hash=hash_ip_for_logs(
                getattr(request.state, "client_ip", "unknown")
            ),
            request_path=request.url.path,
            webhook_url=subtitle_req.webhook_url,
        )
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=202,
            content=ExtractionQueuedResponse(
                job_id=job_id,
                video_id=video_id,
                language=subtitle_req.language,
                webhook_url=subtitle_req.webhook_url,
            ).model_dump(),
        )

    except ErrorCodeException:
        raise
    except Exception as e:
        logger.error(f"Error processing subtitle request: {e}", exc_info=True)
        raise ErrorCodeException(error_code="INTERNAL_ERROR")


@router.post("/subtitles", summary="Extract subtitles", operation_id="extract_subtitles")
async def create_subtitles(request: Request, subtitle_req: SubtitleRequest):
    """API-spec endpoint: extract subtitles or enqueue an async job.

    Webhook support: Optionally provide a `webhook_url` to receive a POST
    notification when the job completes. The webhook payload includes job
    status, result data, and HMAC signature for verification.
    """
    return await _extract_or_enqueue(request, subtitle_req)


@router.post(
    "/rewrite-video",
    summary="Rewrite video (deprecated)",
    deprecated=True,
    operation_id="rewrite_video",
)
async def rewrite_video(request: Request, subtitle_req: SubtitleRequest):
    """Back-compat endpoint (alias of `POST /api/v1/subtitles`). Use POST /subtitles instead."""
    return await _extract_or_enqueue(request, subtitle_req)


@router.get(
    "/subtitles/{video_id}",
    summary="Get cached subtitles",
    operation_id="get_subtitles",
)
async def get_subtitles(
    request: Request,
    video_id: str,
    language: str = Query("en", description="Subtitle language code"),
):
    """
    Get cached subtitles for a video.

    Returns cached result if available, otherwise 404.
    Use POST /subtitles to trigger extraction if not cached.
    """
    if not re.match(VIDEO_ID_PATTERN, video_id):
        raise ErrorCodeException(
            error_code="INVALID_VIDEO_ID",
            detail=f"Invalid video ID format: {video_id}",
        )

    from src.services.security import require_api_key_if_configured

    require_api_key_if_configured(request)
    orchestrator = request.state.subtitle_orchestrator
    cached_result = await orchestrator.get_cached(video_id=video_id, language=language)
    if cached_result:
        return cached_result

    raise ErrorCodeException(
        error_code="SUBTITLE_NOT_FOUND",
        detail=f"Subtitles not found for video {video_id} in language {language}",
        meta={"video_id": video_id, "language": language},
    )


class BatchRequest(BaseModel):
    video_ids: list[str] = Field(..., max_length=100, min_length=1)
    language: str = "en"
    clean_for_ai: bool = True
    webhook_url: Optional[str] = Field(
        default=None,
        description="Optional webhook URL to receive job completion notifications for all jobs",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "video_ids": ["dQw4w9WgXcQ", "anotherVideoId"],
                "language": "en",
                "clean_for_ai": True,
                "webhook_url": "https://example.com/webhook",
            }
        }
    )

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        # Validate webhook URL format
        try:
            parsed = urlparse(v)
            if not parsed.scheme or parsed.scheme not in ("http", "https"):
                raise ValueError("Webhook URL must use http or https scheme")
            if not parsed.netloc:
                raise ValueError("Webhook URL must have a valid host")
        except Exception as e:
            raise ValueError(f"Invalid webhook URL: {e}")
        return v


@router.post(
    "/subtitles/batch",
    summary="Batch subtitle extraction",
    operation_id="batch_subtitles",
)
async def batch_extraction(request: Request, body: BatchRequest) -> dict[str, Any]:
    """
    Request batch subtitle extraction for multiple videos.

    Returns job IDs for async tracking. Videos with cached results
    are returned immediately without queueing.

    Webhook support: Optionally provide a `webhook_url` to receive
    notifications when each job completes.
    """
    from src.services.security import require_api_key_if_configured, hash_ip_for_logs

    require_api_key_if_configured(request)
    # Validate all video IDs
    invalid_ids = [vid for vid in body.video_ids if not re.match(VIDEO_ID_PATTERN, vid)]
    if invalid_ids:
        raise ErrorCodeException(
            error_code="INVALID_VIDEO_ID",
            detail=f"Invalid video IDs: {', '.join(invalid_ids[:5])}",
            meta={"invalid_count": len(invalid_ids), "sample_invalid_ids": invalid_ids[:5]},
        )

    orchestrator = request.state.subtitle_orchestrator
    job_ids: list[str] = []
    cached: list[str] = []

    # PERFORMANCE: Use batch cache lookup instead of N individual lookups
    # This eliminates the N+1 query problem by using Redis MGET
    cache_results = await orchestrator.get_cached_batch(
        video_ids=body.video_ids, language=body.language
    )

    for vid in body.video_ids:
        hit = cache_results.get(vid)
        if hit:
            cached.append(vid)
            continue
        job_id = await orchestrator.enqueue_extraction(
            video_id=vid,
            language=body.language,
            clean_for_ai=body.clean_for_ai,
            client_ip_hash=hash_ip_for_logs(
                getattr(request.state, "client_ip", "unknown")
            ),
            request_path=request.url.path,
            webhook_url=body.webhook_url,
        )
        job_ids.append(job_id)

    return {
        "status": "queued",
        "video_count": len(body.video_ids),
        "queued_count": len(job_ids),
        "cached_count": len(cached),
        "job_ids": job_ids,
        "cached": cached,
    }


@router.get(
    "/job/{job_id}",
    summary="Get job status",
    operation_id="get_job_status",
    responses={
        200: {"description": "Job status retrieved"},
        404: {"description": "Job not found"},
    },
)
async def job_status(
    request: Request, job_id: str
) -> dict[str, Any]:
    """Get the status of an asynchronous subtitle extraction job."""
    from src.services.security import require_api_key_if_configured

    require_api_key_if_configured(request)
    orchestrator = request.state.subtitle_orchestrator
    return await orchestrator.get_job(job_id=job_id)
