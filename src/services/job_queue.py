from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import redis
from rq import Queue
from rq.job import Job


@dataclass(frozen=True)
class QueueConfig:
    redis_url: str
    queue_name: str
    default_timeout: int
    result_ttl: int


def get_redis_connection(redis_url: str) -> redis.Redis:
    # RQ stores pickled job payloads in Redis; keep raw bytes for correctness.
    return redis.Redis.from_url(redis_url)


def get_queue(cfg: QueueConfig) -> Queue:
    conn = get_redis_connection(cfg.redis_url)
    return Queue(
        name=cfg.queue_name, connection=conn, default_timeout=cfg.default_timeout
    )


def enqueue_job(
    *,
    cfg: QueueConfig,
    func_path: str,
    kwargs: dict[str, Any],
    job_id: Optional[str] = None,
) -> str:
    queue = get_queue(cfg)
    job = queue.enqueue_call(
        func=func_path,
        kwargs=kwargs,
        job_id=job_id,
        result_ttl=cfg.result_ttl,
        ttl=cfg.result_ttl,
        failure_ttl=cfg.result_ttl,
    )
    return job.id


def fetch_job(cfg: QueueConfig, job_id: str) -> Optional[Job]:
    conn = get_redis_connection(cfg.redis_url)
    try:
        return Job.fetch(job_id, connection=conn)
    except Exception:
        return None


def queue_stats(cfg: QueueConfig) -> dict[str, Any]:
    q = get_queue(cfg)

    def _count(reg) -> int:
        c = getattr(reg, "count", 0)
        return int(c() if callable(c) else c)

    started = _count(q.started_job_registry)
    failed = _count(q.failed_job_registry)
    deferred = _count(q.deferred_job_registry)
    scheduled = _count(q.scheduled_job_registry)
    return {
        "queue_name": q.name,
        "queue_depth": q.count,
        "started_jobs": started,
        "failed_jobs": failed,
        "deferred_jobs": deferred,
        "scheduled_jobs": scheduled,
    }
