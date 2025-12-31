"""
Cache management using Redis.
Implements multi-tier caching strategy with TTL support.
"""

import json
import logging
import hashlib
from typing import Optional, Any

import redis.asyncio as redis
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages distributed caching using Redis."""

    def __init__(self, redis_url: str):
        """Initialize cache manager."""
        self.redis_url = redis_url
        self.redis: Optional[Redis] = None

    async def connect(self):
        """Connect to Redis."""
        try:
            self.redis = await redis.from_url(self.redis_url, decode_responses=True)
            await self.redis.ping()
            logger.info("Connected to Redis cache")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis:
            aclose = getattr(self.redis, "aclose", None)
            if callable(aclose):
                await aclose()
            else:
                await self.redis.close()
            logger.info("Disconnected from Redis")

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.redis:
            return None

        try:
            value = await self.redis.get(key)
            if value:
                logger.debug(f"Cache hit for key: {key}")
                return json.loads(value)
            logger.debug(f"Cache miss for key: {key}")
            return None
        except Exception as e:
            logger.error(f"Cache get error for {key}: {e}")
            return None

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        """
        Get multiple values from cache in a single batch operation.

        PERFORMANCE: Uses Redis MGET to retrieve multiple keys in one network
        round-trip instead of N individual GET commands. This eliminates the
        N+1 query problem in batch operations.
        """
        if not self.redis or not keys:
            return {}

        try:
            values = await self.redis.mget(keys)
            result = {}
            for key, value in zip(keys, values):
                if value:
                    try:
                        result[key] = json.loads(value)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to decode cached value for key: {key}")
            logger.debug(f"Batch cache get: {len(result)}/{len(keys)} hits")
            return result
        except Exception as e:
            logger.error(f"Batch cache get error: {e}")
            return {}

    async def set(self, key: str, value: Any, ttl_seconds: int = 3600):
        """Set value in cache with TTL."""
        if not self.redis:
            return

        try:
            serialized = json.dumps(value, default=str)
            await self.redis.setex(key, ttl_seconds, serialized)
            logger.debug(f"Cached {key} with TTL {ttl_seconds}s")
        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self.redis:
            return False

        try:
            deleted = await self.redis.delete(key)
            logger.debug(f"Deleted cache key: {key}")
            return bool(deleted)
        except Exception as e:
            logger.error(f"Cache delete error for {key}: {e}")
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern (SCAN-based, safe for production)."""
        if not self.redis:
            return 0

        try:
            deleted = 0
            batch: list[str] = []
            async for key in self.redis.scan_iter(match=pattern, count=500):
                batch.append(key)
                if len(batch) >= 500:
                    deleted += int(await self.redis.delete(*batch))
                    batch.clear()
            if batch:
                deleted += int(await self.redis.delete(*batch))

            if deleted:
                logger.info(
                    "cache_clear_pattern",
                    extra={"pattern": pattern, "deleted": deleted},
                )
            return deleted
        except Exception as e:
            logger.error(f"Cache clear pattern error: {e}")
            return 0

    async def incr(self, key: str, amount: int = 1) -> int:
        """Increment counter in cache."""
        if not self.redis:
            return 0

        try:
            value = await self.redis.incrby(key, amount)
            return value
        except Exception as e:
            logger.error(f"Cache increment error for {key}: {e}")
            return 0

    async def set_if_not_exists(
        self, key: str, value: Any, ttl_seconds: int = 3600
    ) -> bool:
        """Set value only if key doesn't exist (atomic)."""
        if not self.redis:
            return False

        try:
            serialized = json.dumps(value, default=str)
            result = await self.redis.set(key, serialized, ex=ttl_seconds, nx=True)
            return result is not None
        except Exception as e:
            logger.error(f"Cache set_if_not_exists error for {key}: {e}")
            return False

    async def acquire_lock(
        self, lock_key: str, ttl_seconds: int = 30
    ) -> bool:
        """
        Acquire a distributed lock using SET NX EX (atomic).

        STAMPEDE PROTECTION: Used to prevent multiple workers from simultaneously
        regenerating the same cached value when a cache miss occurs. Only one
        worker acquires the lock and performs the expensive operation; others
        wait and reuse the result.
        """
        if not self.redis:
            return False

        try:
            result = await self.redis.set(
                lock_key, "1", ex=ttl_seconds, nx=True
            )
            return result is not None
        except Exception as e:
            logger.error(f"Lock acquisition error for {lock_key}: {e}")
            return False

    async def release_lock(self, lock_key: str) -> bool:
        """Release a distributed lock."""
        if not self.redis:
            return False

        try:
            deleted = await self.redis.delete(lock_key)
            return bool(deleted)
        except Exception as e:
            logger.error(f"Lock release error for {lock_key}: {e}")
            return False

    def generate_cache_key(self, video_id: str, suffix: str = "") -> str:
        """Generate cache key for video."""
        key = f"youtube:subtitle:{video_id}"
        if suffix:
            key = f"{key}:{suffix}"
        return key

    def generate_rate_limit_key(self, client_ip: str, endpoint: str) -> str:
        """Generate rate limit tracking key."""
        endpoint_hash = hashlib.md5(endpoint.encode()).hexdigest()[:8]
        return f"ratelimit:{client_ip}:{endpoint_hash}"
