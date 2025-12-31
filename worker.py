"""
RQ Worker entrypoint for YouTube Subtitle API.

Starts N worker processes (WORKER_CONCURRENCY) that consume jobs from REDIS_QUEUE_NAME.
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing as mp
import os
import signal
import sys

import redis
from rq import Connection, Worker

from src.core.config import settings
from src.core.logging_config import setup_logging
from src.worker.context import init_worker_context, shutdown_worker_context


def _run_worker_process() -> None:
    setup_logging(level=settings.LOG_LEVEL)
    logger = logging.getLogger(__name__)

    asyncio.run(init_worker_context())

    # RQ expects to read/write binary payloads in Redis; do not enable decoding.
    conn = redis.Redis.from_url(settings.REDIS_URL)

    def _shutdown(_signum, _frame):
        logger.info("worker_shutdown_signal")
        try:
            asyncio.run(shutdown_worker_context())
        finally:
            sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    with Connection(conn):
        worker = Worker([settings.REDIS_QUEUE_NAME])
        logger.info("worker_started", extra={"queue": settings.REDIS_QUEUE_NAME})
        worker.work(with_scheduler=True)


def main() -> None:
    concurrency = max(
        1, int(os.getenv("WORKER_CONCURRENCY", str(settings.WORKER_CONCURRENCY)))
    )
    procs: list[mp.Process] = []
    for _ in range(concurrency):
        p = mp.Process(target=_run_worker_process, daemon=False)
        p.start()
        procs.append(p)

    for p in procs:
        p.join()


if __name__ == "__main__":
    main()
