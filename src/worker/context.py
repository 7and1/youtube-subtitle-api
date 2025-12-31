from __future__ import annotations

import logging

from src.core.config import settings
from src.services.cache import CacheManager
from src.services.database import DatabaseManager

logger = logging.getLogger(__name__)

cache_manager: CacheManager | None = None
db_manager: DatabaseManager | None = None


async def init_worker_context() -> None:
    global cache_manager, db_manager

    cache_manager = CacheManager(redis_url=settings.REDIS_URL)
    await cache_manager.connect()

    db_manager = DatabaseManager(
        database_url=settings.DATABASE_URL,
        db_schema=settings.DB_SCHEMA,
        pool_size=settings.WORKER_DB_POOL_SIZE,
        pool_min_size=1,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        echo=False,
    )
    await db_manager.connect()
    await db_manager.init_schema(create_tables=settings.DB_AUTO_CREATE)
    logger.info("worker_context_ready")


async def shutdown_worker_context() -> None:
    global cache_manager, db_manager
    if cache_manager:
        await cache_manager.disconnect()
    if db_manager:
        await db_manager.disconnect()
