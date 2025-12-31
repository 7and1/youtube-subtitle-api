from __future__ import annotations

import logging
import time

from src.core.config import settings
from tenacity import retry, stop_after_attempt, wait_exponential
from src.core.time_utils import utc_now_iso_z
from src.services.proxy_pool import choose_proxy, mark_proxy_failure, mark_proxy_success
from src.services.subtitle_repository import SubtitleRepository
from src.services.webhook import send_webhook_sync, WebhookDeliveryResult
from src.services.youtube_extractor import extract_subtitles_dual_engine
from src.worker import context as ctx
from src.metrics import (
    extraction_duration_seconds,
    extraction_failure_total,
    extraction_success_total,
)

logger = logging.getLogger(__name__)


async def _update_job_status(
    job_id: str, status: str, result: dict | None = None, error: str | None = None
) -> None:
    async with ctx.db_manager.get_session() as session:
        repo = SubtitleRepository(session)
        await repo.update_job_status(
            job_id=job_id, status=status, result_data=result, error_message=error
        )


async def _send_webhook_notification(
    job_id: str,
    video_id: str,
    status: str,
    result: dict | None = None,
    error: str | None = None,
) -> WebhookDeliveryResult | None:
    """
    Send webhook notification for job completion if webhook_url is configured.

    Returns WebhookDeliveryResult if webhook was configured, None otherwise.
    """
    # Get the job to check for webhook_url
    async with ctx.db_manager.get_session() as session:
        repo = SubtitleRepository(session)
        job = await repo.get_job_by_id(job_id)

    if not job or not job.webhook_url:
        return None

    try:
        delivery_result = send_webhook_sync(
            webhook_url=job.webhook_url,
            job_id=job_id,
            video_id=video_id,
            status=status,
            result=result,
            error=error,
        )

        # Update webhook delivery status in database
        async with ctx.db_manager.get_session() as session:
            repo = SubtitleRepository(session)
            await repo.update_webhook_delivery(
                job_id=job_id,
                delivered=delivery_result.success,
                status="delivered" if delivery_result.success else "failed",
                error=delivery_result.error,
            )

        return delivery_result

    except Exception as e:
        logger.error(
            "webhook_send_exception",
            extra={
                "job_id": job_id,
                "video_id": video_id,
                "error": str(e),
            },
        )

        # Update webhook delivery status as failed
        async with ctx.db_manager.get_session() as session:
            repo = SubtitleRepository(session)
            await repo.update_webhook_delivery(
                job_id=job_id,
                delivered=False,
                status="failed",
                error=str(e)[:500],
            )

        return None


def extract_subtitles_job(
    video_id: str,
    language: str = "en",
    clean_for_ai: bool = True,
    client_ip_hash: str = "",
):
    """
    RQ job entrypoint (sync).

    Uses asyncio internally so it can share the async DB/Redis stack with the API.
    """
    import asyncio

    return asyncio.run(
        _extract_subtitles_job_async(video_id, language, clean_for_ai, client_ip_hash)
    )


async def _extract_subtitles_job_async(
    video_id: str,
    language: str,
    clean_for_ai: bool,
    client_ip_hash: str,
) -> dict:
    if ctx.cache_manager is None or ctx.db_manager is None:
        raise RuntimeError(
            "Worker context not initialized (cache_manager/db_manager missing)"
        )

    from rq import get_current_job

    rq_job = get_current_job()
    job_id = rq_job.id if rq_job else ""

    await _update_job_status(job_id, "processing")

    started = time.time()
    proxy = (
        await choose_proxy(ctx.cache_manager.redis) if settings.YT_PROXY_URLS else None
    )
    proxy_url = proxy.url if proxy else None
    proxy_dict = {"http": proxy_url, "https": proxy_url} if proxy_url else None

    @retry(
        stop=stop_after_attempt(max(1, settings.YT_RETRY_MAX_ATTEMPTS)),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        reraise=True,
    )
    async def _run_extraction():
        return await extract_subtitles_dual_engine(
            video_id=video_id,
            language=language,
            timeout=settings.YT_EXTRACTION_TIMEOUT,
            use_proxy=bool(proxy_url),
            proxy_url=proxy_url,
            proxy_dict=proxy_dict,
            fallback_enabled=True,
            clean_for_ai=clean_for_ai,
        )

    try:
        extracted = await _run_extraction()

        duration_ms = int((time.time() - started) * 1000)
        extraction_success_total.labels(method=extracted.extraction_method).inc()
        extraction_duration_seconds.labels(method=extracted.extraction_method).observe(
            duration_ms / 1000.0
        )

        payload = {
            "success": True,
            "video_id": extracted.video_id,
            "title": extracted.title,
            "language": extracted.language,
            "extraction_method": extracted.extraction_method,
            "subtitle_count": len(extracted.subtitles),
            "duration_ms": duration_ms,
            "cached": False,
            "subtitles": extracted.subtitles,
            "plain_text": extracted.plain_text,
            "proxy_used": extracted.proxy_used,
            "created_at": utc_now_iso_z(),
        }

        async with ctx.db_manager.get_session() as session:
            repo = SubtitleRepository(session)
            await repo.upsert_subtitle_record(
                video_id=video_id,
                language=language,
                title=extracted.title,
                subtitles=extracted.subtitles,
                plain_text=extracted.plain_text,
                extraction_method=extracted.extraction_method,
                extraction_duration_ms=duration_ms,
                proxy_used=extracted.proxy_used,
            )

        cache_key = ctx.cache_manager.generate_cache_key(video_id, suffix=language)
        await ctx.cache_manager.set(
            cache_key, payload, ttl_seconds=settings.REDIS_RESULT_TTL
        )

        await _update_job_status(job_id, "completed", result=payload)

        # Send webhook notification if configured
        await _send_webhook_notification(
            job_id=job_id,
            video_id=video_id,
            status="success",
            result=payload,
        )

        if proxy and extracted.proxy_used:
            await mark_proxy_success(ctx.cache_manager.redis, proxy)

        logger.info(
            "extraction_completed",
            extra={
                "video_id": video_id,
                "language": language,
                "method": extracted.extraction_method,
                "duration_ms": duration_ms,
                "proxy_used": extracted.proxy_used,
                "client_ip_hash": client_ip_hash,
            },
        )

        return payload

    except Exception as e:
        err = str(e)
        extraction_failure_total.labels(method="unknown").inc()
        await _update_job_status(job_id, "failed", error=err)

        # Send webhook notification for failure if configured
        await _send_webhook_notification(
            job_id=job_id,
            video_id=video_id,
            status="failed",
            error=err,
        )

        if proxy:
            await mark_proxy_failure(ctx.cache_manager.redis, proxy)
        logger.error("extraction_failed", extra={"video_id": video_id, "error": err})
        raise
