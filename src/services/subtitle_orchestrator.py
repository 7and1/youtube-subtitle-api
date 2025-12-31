from __future__ import annotations

import asyncio
from typing import Any, Optional

import anyio

from src.core.config import settings
from src.metrics import cache_hits_total, cache_misses_total, extraction_requests_total
from src.services.cache import CacheManager
from src.services.database import DatabaseManager
from src.services.in_memory_cache import InMemoryCache
from src.services.job_queue import QueueConfig, enqueue_job, fetch_job
from src.services.subtitle_repository import SubtitleRepository


class SubtitleOrchestrator:
    def __init__(
        self,
        *,
        memory_cache: InMemoryCache,
        cache_manager: CacheManager,
        db_manager: DatabaseManager,
        queue_cfg: QueueConfig,
    ):
        self.memory_cache = memory_cache
        self.cache_manager = cache_manager
        self.db_manager = db_manager
        self.queue_cfg = queue_cfg

    def _cache_key(self, video_id: str, language: str) -> str:
        return self.cache_manager.generate_cache_key(video_id, suffix=language)

    def _lock_key(self, video_id: str, language: str) -> str:
        """Generate lock key for cache stampede protection."""
        return f"lock:youtube:subtitle:{video_id}:{language}"

    async def get_cached(
        self, *, video_id: str, language: str
    ) -> Optional[dict[str, Any]]:
        key = self._cache_key(video_id, language)
        lock_key = self._lock_key(video_id, language)

        # Tier 1: in-memory
        mem = await self.memory_cache.get(key)
        if mem:
            cache_hits_total.labels(tier="memory").inc()
            return {**mem, "cached": True, "cache_tier": "memory"}

        # Tier 2: Redis
        redis_val = await self.cache_manager.get(key)
        if redis_val:
            cache_hits_total.labels(tier="redis").inc()
            await self.memory_cache.set(key, redis_val)
            return {**redis_val, "cached": True, "cache_tier": "redis"}

        # Tier 3: PostgreSQL with cache stampede protection
        # STAMPEDE PROTECTION: Use distributed lock to prevent multiple workers
        # from simultaneously querying the database for the same miss. Only one
        # worker performs the query; others wait briefly and retry.
        lock_acquired = await self.cache_manager.acquire_lock(lock_key)

        if lock_acquired:
            try:
                # Double-check cache after acquiring lock (another worker may
                # have populated it while we waited)
                redis_val = await self.cache_manager.get(key)
                if redis_val:
                    cache_hits_total.labels(tier="redis").inc()
                    await self.memory_cache.set(key, redis_val)
                    return {**redis_val, "cached": True, "cache_tier": "redis"}

                # Perform the database query
                async with self.db_manager.get_session() as session:
                    repo = SubtitleRepository(session)
                    rec = await repo.get_subtitle_record(video_id, language)
                    if not rec or rec.extraction_status != "success":
                        cache_misses_total.inc()
                        return None

                    payload = {
                        "success": True,
                        "video_id": rec.video_id,
                        "title": rec.title,
                        "language": rec.language,
                        "extraction_method": rec.extraction_method,
                        "subtitle_count": len(rec.subtitles or []),
                        "duration_ms": int(rec.extraction_duration_ms or 0),
                        "subtitles": rec.subtitles or [],
                        "plain_text": rec.plain_text,
                        "proxy_used": rec.proxy_used,
                        "created_at": rec.created_at.isoformat() + "Z",
                    }

                cache_hits_total.labels(tier="postgres").inc()
                await self.cache_manager.set(
                    key, payload, ttl_seconds=settings.REDIS_RESULT_TTL
                )
                await self.memory_cache.set(key, payload)
                return {**payload, "cached": True, "cache_tier": "postgres"}
            finally:
                await self.cache_manager.release_lock(lock_key)
        else:
            # Another worker is fetching the data. Wait briefly and retry.
            # STAMPEDE PROTECTION: Back off to allow the lock holder to complete
            await asyncio.sleep(0.1)
            redis_val = await self.cache_manager.get(key)
            if redis_val:
                cache_hits_total.labels(tier="redis").inc()
                await self.memory_cache.set(key, redis_val)
                return {**redis_val, "cached": True, "cache_tier": "redis"}
            # If still not available after waiting, return None
            cache_misses_total.inc()
            return None

    async def get_cached_batch(
        self, *, video_ids: list[str], language: str
    ) -> dict[str, Optional[dict[str, Any]]]:
        """
        Batch cache lookup for multiple videos with the same language.

        PERFORMANCE: Uses Redis MGET for single-round-trip batch retrieval
        instead of N individual GET calls. Returns dict mapping video_id to
        cached data (or None if not found).
        """
        keys = [self._cache_key(vid, language) for vid in video_ids]
        result: dict[str, Optional[dict[str, Any]]] = {vid: None for vid in video_ids}

        # Tier 1: in-memory batch
        mem_hits = await self.memory_cache.get_many(keys)
        for vid, key in zip(video_ids, keys):
            if key in mem_hits:
                cache_hits_total.labels(tier="memory").inc()
                result[vid] = {**mem_hits[key], "cached": True, "cache_tier": "memory"}

        # Filter keys that weren't in memory cache
        remaining_keys = [k for k in keys if k not in mem_hits]
        if not remaining_keys:
            return result

        # Tier 2: Redis batch
        redis_hits = await self.cache_manager.get_many(remaining_keys)
        for vid, key in zip(video_ids, keys):
            if key in redis_hits and result[vid] is None:
                cache_hits_total.labels(tier="redis").inc()
                # Populate memory cache for future hits
                await self.memory_cache.set(key, redis_hits[key])
                result[vid] = {**redis_hits[key], "cached": True, "cache_tier": "redis"}

        return result

    async def enqueue_extraction(
        self,
        *,
        video_id: str,
        language: str,
        clean_for_ai: bool,
        client_ip_hash: str,
        request_path: str,
        webhook_url: Optional[str] = None,
    ) -> str:
        extraction_requests_total.labels(endpoint=request_path).inc()

        async with self.db_manager.get_session() as session:
            repo = SubtitleRepository(session)
            existing = await repo.get_pending_job(video_id, language)
            if existing:
                # Avoid returning stale jobs (e.g. Redis flushed/restarted).
                rq_job = await anyio.to_thread.run_sync(
                    lambda: fetch_job(self.queue_cfg, existing.job_id)
                )
                if rq_job is not None:
                    return existing.job_id
                await repo.update_job_status(
                    job_id=existing.job_id,
                    status="stale",
                    error_message="rq_job_missing",
                )

        kwargs = {
            "video_id": video_id,
            "language": language,
            "clean_for_ai": clean_for_ai,
            "client_ip_hash": client_ip_hash,
        }

        job_id = await anyio.to_thread.run_sync(
            lambda: enqueue_job(
                cfg=self.queue_cfg,
                func_path="src.worker.tasks.extract_subtitles_job",
                kwargs=kwargs,
            )
        )

        async with self.db_manager.get_session() as session:
            repo = SubtitleRepository(session)
            await repo.create_job(
                video_id=video_id,
                language=language,
                job_id=job_id,
                webhook_url=webhook_url,
            )

        return job_id

    async def get_job(self, *, job_id: str) -> dict[str, Any]:
        job = await anyio.to_thread.run_sync(lambda: fetch_job(self.queue_cfg, job_id))
        if not job:
            return {"job_id": job_id, "status": "not_found"}

        result = job.result if job.is_finished else None
        status = job.get_status()
        return {
            "job_id": job.id,
            "status": status,
            "enqueued_at": (
                job.enqueued_at.isoformat() + "Z" if job.enqueued_at else None
            ),
            "ended_at": job.ended_at.isoformat() + "Z" if job.ended_at else None,
            "result": result,
            "exc_info": job.exc_info if job.is_failed else None,
        }
