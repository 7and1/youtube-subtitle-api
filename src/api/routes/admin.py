"""
Admin endpoints for cache management and monitoring.
"""

import logging

import anyio
from fastapi import APIRouter, Request, HTTPException, Query

from src.core.time_utils import utc_now_iso_z
from src.api.middleware import ErrorCodeException

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/cache/clear",
    summary="Clear all cache",
    operation_id="admin_clear_cache",
)
async def clear_cache(request: Request, purge_db: bool = Query(False, description="Also clear database records")):
    """
    Clear in-memory and Redis cache.

    By default, only clears cache (memory + Redis). Set purge_db=true
    to also delete subtitle records from PostgreSQL.
    """
    from src.services.security import require_admin_auth

    require_admin_auth(request)
    cache_manager = request.state.cache_manager
    memory_cache = request.state.memory_cache

    try:
        await memory_cache.clear()
        await cache_manager.clear_pattern("youtube:subtitle:*")
        deleted_db = 0
        if purge_db:
            async with request.state.db_manager.get_session() as session:
                from src.services.subtitle_repository import SubtitleRepository

                deleted_db = await SubtitleRepository(session).clear_cache_records()

        return {
            "status": "cleared",
            "message": "Cache cleared",
            "purge_db": purge_db,
            "deleted_db_records": deleted_db,
            "timestamp": utc_now_iso_z(),
        }
    except Exception as e:
        logger.error(f"Cache clear error: {e}", exc_info=True)
        raise ErrorCodeException(
            error_code="INTERNAL_ERROR",
            detail="Cache clear operation failed",
        )


@router.delete(
    "/cache/clear/{video_id}",
    summary="Clear video cache",
    operation_id="admin_clear_video_cache",
)
async def clear_video_cache(
    request: Request,
    video_id: str,
    language: str = Query(None, description="Specific language to clear (omits to clear all)"),
):
    """Clear cache for a specific video from in-memory and Redis."""
    from src.services.security import require_admin_auth

    require_admin_auth(request)
    cache_manager = request.state.cache_manager
    memory_cache = request.state.memory_cache

    try:
        keys = []
        if language:
            keys.append(cache_manager.generate_cache_key(video_id, suffix=language))
        else:
            # Best-effort: delete common language keys and a wildcard match in Redis.
            for lang in (
                "en",
                "zh",
                "zh-Hans",
                "zh-Hant",
                "es",
                "fr",
                "de",
                "ja",
                "ko",
            ):
                keys.append(cache_manager.generate_cache_key(video_id, suffix=lang))

        deleted_any = False
        for k in keys:
            deleted_any = (await cache_manager.delete(k)) or deleted_any
            await memory_cache.delete(k)

        if not language:
            await cache_manager.clear_pattern(f"youtube:subtitle:{video_id}:*")

        return {
            "status": "deleted" if deleted_any else "not_found",
            "video_id": video_id,
            "language": language,
            "timestamp": utc_now_iso_z(),
        }
    except Exception as e:
        logger.error(f"Cache delete error for {video_id}: {e}", exc_info=True)
        raise ErrorCodeException(
            error_code="INTERNAL_ERROR",
            detail=f"Failed to clear cache for video {video_id}",
            meta={"video_id": video_id},
        )


@router.get(
    "/queue/stats",
    summary="Get queue statistics",
    operation_id="admin_queue_stats",
)
async def queue_stats(request: Request):
    """Get job queue statistics including depth and worker status."""
    from src.services.security import require_admin_auth

    require_admin_auth(request)
    from src.core.config import settings
    from src.services.job_queue import QueueConfig, queue_stats as get_stats

    try:
        cfg = QueueConfig(
            redis_url=settings.REDIS_URL,
            queue_name=settings.REDIS_QUEUE_NAME,
            default_timeout=settings.YT_EXTRACTION_TIMEOUT + 10,
            result_ttl=settings.REDIS_RESULT_TTL,
        )
        stats = await anyio.to_thread.run_sync(lambda: get_stats(cfg))
        return {**stats, "timestamp": utc_now_iso_z()}
    except Exception as e:
        logger.error(f"Queue stats error: {e}", exc_info=True)
        raise ErrorCodeException(
            error_code="INTERNAL_ERROR",
            detail="Failed to retrieve queue statistics",
        )


@router.get(
    "/rate-limit/stats/{client_ip}",
    summary="Get client rate limit stats",
    operation_id="admin_rate_limit_stats",
)
async def get_client_rate_limit(request: Request, client_ip: str):
    """
    Get rate limit statistics for a specific client IP.

    Shows remaining requests and reset times for each endpoint.
    """
    from src.services.security import require_admin_auth

    require_admin_auth(request)
    rate_limiter = request.state.rate_limiter

    try:
        stats = await rate_limiter.get_stats(client_ip)
        return {
            "client_ip": client_ip,
            "endpoints": stats,
            "timestamp": utc_now_iso_z(),
        }
    except Exception as e:
        logger.error(f"Rate limit stats error: {e}", exc_info=True)
        raise ErrorCodeException(
            error_code="INTERNAL_ERROR",
            detail=f"Failed to retrieve rate limit stats for {client_ip}",
        )


@router.post(
    "/rate-limit/reset/{client_ip}",
    summary="Reset client rate limit",
    operation_id="admin_reset_rate_limit",
)
async def reset_client_rate_limit(request: Request, client_ip: str):
    """
    Reset rate limit for a specific client IP.

    This allows the client to make fresh requests immediately.
    Use with caution - this bypasses rate limit protections.
    """
    from src.services.security import require_admin_auth

    require_admin_auth(request)
    rate_limiter = request.state.rate_limiter

    try:
        await rate_limiter.reset_for_client(client_ip)
        return {
            "status": "reset",
            "client_ip": client_ip,
            "message": f"Rate limit reset for {client_ip}",
            "timestamp": utc_now_iso_z(),
        }
    except Exception as e:
        logger.error(f"Rate limit reset error for {client_ip}: {e}", exc_info=True)
        raise ErrorCodeException(
            error_code="INTERNAL_ERROR",
            detail=f"Failed to reset rate limit for {client_ip}",
        )
