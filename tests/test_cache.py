"""
Cache layer tests for in-memory and Redis caching.

Tests cover:
- In-memory cache operations (get, set, delete, clear)
- Redis cache operations
- Cache stampede protection via distributed locks
- Batch cache operations
- TTL behavior
- Error handling
"""

from __future__ import annotations

import asyncio
import json
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from cachetools import TTLCache

from src.services.in_memory_cache import InMemoryCache, CacheStats
from src.services.cache import CacheManager


class TestInMemoryCache:
    """Tests for InMemoryCache (Tier 1 cache)."""

    @pytest.mark.asyncio
    async def test_get_set_single_value(self):
        """Test basic get and set operations."""
        cache = InMemoryCache(maxsize=100, ttl_seconds=60)

        # Set a value
        await cache.set("key1", {"data": "value1"})

        # Get the value
        result = await cache.get("key1")
        assert result == {"data": "value1"}

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self):
        """Test getting a key that doesn't exist."""
        cache = InMemoryCache(maxsize=100, ttl_seconds=60)

        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_overwrites_existing(self):
        """Test that set overwrites existing value."""
        cache = InMemoryCache(maxsize=100, ttl_seconds=60)

        await cache.set("key1", {"data": "value1"})
        await cache.set("key1", {"data": "value2"})

        result = await cache.get("key1")
        assert result == {"data": "value2"}

    @pytest.mark.asyncio
    async def test_delete_existing_key(self):
        """Test deleting an existing key."""
        cache = InMemoryCache(maxsize=100, ttl_seconds=60)

        await cache.set("key1", {"data": "value1"})
        deleted = await cache.delete("key1")

        assert deleted is True
        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_key(self):
        """Test deleting a key that doesn't exist."""
        cache = InMemoryCache(maxsize=100, ttl_seconds=60)

        deleted = await cache.delete("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_clear_all_keys(self):
        """Test clearing all keys from cache."""
        cache = InMemoryCache(maxsize=100, ttl_seconds=60)

        await cache.set("key1", {"data": "value1"})
        await cache.set("key2", {"data": "value2"})
        await cache.set("key3", {"data": "value3"})

        await cache.clear()

        assert await cache.get("key1") is None
        assert await cache.get("key2") is None
        assert await cache.get("key3") is None

    @pytest.mark.asyncio
    async def test_size_returns_count(self):
        """Test that size returns the count of items."""
        cache = InMemoryCache(maxsize=100, ttl_seconds=60)

        assert await cache.size() == 0

        await cache.set("key1", {"data": "value1"})
        assert await cache.size() == 1

        await cache.set("key2", {"data": "value2"})
        assert await cache.size() == 2

        await cache.delete("key1")
        assert await cache.size() == 1

    @pytest.mark.asyncio
    async def test_get_many_batch_retrieval(self):
        """Test batch retrieval of multiple keys."""
        cache = InMemoryCache(maxsize=100, ttl_seconds=60)

        await cache.set("key1", {"data": "value1"})
        await cache.set("key2", {"data": "value2"})
        await cache.set("key3", {"data": "value3"})

        result = await cache.get_many(["key1", "key2", "key3", "key4"])

        assert result["key1"] == {"data": "value1"}
        assert result["key2"] == {"data": "value2"}
        assert result["key3"] == {"data": "value3"}
        assert "key4" not in result

    @pytest.mark.asyncio
    async def test_cache_stats_tracking(self):
        """Test that cache statistics are tracked correctly."""
        cache = InMemoryCache(maxsize=100, ttl_seconds=60)

        await cache.set("key1", {"data": "value1"})
        await cache.get("key1")  # Hit
        await cache.get("key2")  # Miss

        assert cache.stats.hits == 1
        assert cache.stats.misses == 1
        assert cache.stats.hit_rate == 0.5

    @pytest.mark.asyncio
    async def test_cache_eviction_when_full(self):
        """Test that old items are evicted when cache is full."""
        cache = InMemoryCache(maxsize=2, ttl_seconds=60)

        await cache.set("key1", {"data": "value1"})
        await cache.set("key2", {"data": "value2"})
        await cache.set("key3", {"data": "value3"})  # Should evict key1 or key2

        # Cache should only have 2 items
        assert await cache.size() == 2

    @pytest.mark.asyncio
    async def test_ttl_expiration(self):
        """Test that items expire after TTL."""
        cache = InMemoryCache(maxsize=100, ttl_seconds=1)  # 1 second TTL

        await cache.set("key1", {"data": "value1"})
        assert await cache.get("key1") == {"data": "value1"}

        # Wait for expiration
        await asyncio.sleep(1.1)
        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_concurrent_access_thread_safety(self):
        """Test that cache handles concurrent access safely."""
        cache = InMemoryCache(maxsize=100, ttl_seconds=60)

        # Concurrent sets
        tasks = [cache.set(f"key{i}", {"data": f"value{i}"}) for i in range(50)]
        await asyncio.gather(*tasks)

        # Concurrent gets
        tasks = [cache.get(f"key{i}") for i in range(50)]
        results = await asyncio.gather(*tasks)

        assert all(r is not None for r in results)
        assert await cache.size() == 50


class TestCacheStats:
    """Tests for CacheStats dataclass."""

    def test_initial_stats(self):
        """Test initial statistics values."""
        stats = CacheStats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.hit_rate == 0.0

    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        stats = CacheStats()
        stats.hits = 70
        stats.misses = 30
        assert stats.hit_rate == 0.7

    def test_hit_rate_zero_total(self):
        """Test hit rate when total is zero."""
        stats = CacheStats()
        assert stats.hit_rate == 0.0


class TestRedisCacheManager:
    """Tests for CacheManager (Redis, Tier 2 cache)."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.ping = AsyncMock(return_value=True)
        return redis

    @pytest.mark.asyncio
    async def test_connect_success(self, mock_redis):
        """Test successful connection to Redis."""
        with patch("src.services.cache.redis.from_url", return_value=mock_redis):
            manager = CacheManager(redis_url="redis://localhost:6379/1")
            await manager.connect()

            mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cached_value(self, mock_redis):
        """Test getting a value from cache."""
        cached_data = json.dumps({"video_id": "abc123", "title": "Test Video"})
        mock_redis.get = AsyncMock(return_value=cached_data)

        manager = CacheManager(redis_url="redis://localhost:6379/1")
        manager.redis = mock_redis

        result = await manager.get("youtube:subtitle:abc123:en")

        assert result == {"video_id": "abc123", "title": "Test Video"}

    @pytest.mark.asyncio
    async def test_get_cache_miss(self, mock_redis):
        """Test getting a non-existent key."""
        mock_redis.get = AsyncMock(return_value=None)

        manager = CacheManager(redis_url="redis://localhost:6379/1")
        manager.redis = mock_redis

        result = await manager.get("youtube:subtitle:nonexistent:en")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_invalid_json(self, mock_redis):
        """Test handling of invalid JSON in cache."""
        mock_redis.get = AsyncMock(return_value="not-valid-json")

        manager = CacheManager(redis_url="redis://localhost:6379/1")
        manager.redis = mock_redis

        result = await manager.get("youtube:subtitle:abc123:en")

        assert result is None

    @pytest.mark.asyncio
    async def test_set_value_with_ttl(self, mock_redis):
        """Test setting a value with TTL."""
        manager = CacheManager(redis_url="redis://localhost:6379/1")
        manager.redis = mock_redis

        await manager.set("key1", {"data": "value1"}, ttl_seconds=3600)

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "key1"
        assert call_args[0][1] == 3600

    @pytest.mark.asyncio
    async def test_delete_key(self, mock_redis):
        """Test deleting a key."""
        mock_redis.delete = AsyncMock(return_value=1)

        manager = CacheManager(redis_url="redis://localhost:6379/1")
        manager.redis = mock_redis

        deleted = await manager.delete("key1")

        assert deleted is True
        mock_redis.delete.assert_called_once_with("key1")

    @pytest.mark.asyncio
    async def test_delete_nonexistent_key(self, mock_redis):
        """Test deleting a non-existent key."""
        mock_redis.delete = AsyncMock(return_value=0)

        manager = CacheManager(redis_url="redis://localhost:6379/1")
        manager.redis = mock_redis

        deleted = await manager.delete("nonexistent")

        assert deleted is False

    @pytest.mark.asyncio
    async def test_get_many_batch(self, mock_redis):
        """Test batch get using MGET."""
        mock_redis.mget = AsyncMock(
            return_value=[
                json.dumps({"id": "1"}),
                json.dumps({"id": "2"}),
                None,
                json.dumps({"id": "4"}),
            ]
        )

        manager = CacheManager(redis_url="redis://localhost:6379/1")
        manager.redis = mock_redis

        keys = ["key1", "key2", "key3", "key4"]
        result = await manager.get_many(keys)

        assert len(result) == 3
        assert result["key1"] == {"id": "1"}
        assert result["key2"] == {"id": "2"}
        assert result["key4"] == {"id": "4"}
        assert "key3" not in result

    @pytest.mark.asyncio
    async def test_clear_pattern(self, mock_redis):
        """Test clearing keys by pattern."""
        # Mock scan_iter to return matching keys
        async def mock_scan_iter(match, count):
            yield "youtube:subtitle:abc123:en"
            yield "youtube:subtitle:def456:en"
            yield "youtube:subtitle:ghi789:en"

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.delete = AsyncMock(return_value=3)

        manager = CacheManager(redis_url="redis://localhost:6379/1")
        manager.redis = mock_redis

        deleted = await manager.clear_pattern("youtube:subtitle:*:en")

        assert deleted == 3

    @pytest.mark.asyncio
    async def test_incr_counter(self, mock_redis):
        """Test incrementing a counter."""
        mock_redis.incrby = AsyncMock(return_value=5)

        manager = CacheManager(redis_url="redis://localhost:6379/1")
        manager.redis = mock_redis

        result = await manager.incr("counter_key", amount=2)

        assert result == 5

    @pytest.mark.asyncio
    async def test_set_if_not_exists(self, mock_redis):
        """Test set only if key doesn't exist (NX)."""
        mock_redis.set = AsyncMock(return_value=True)

        manager = CacheManager(redis_url="redis://localhost:6379/1")
        manager.redis = mock_redis

        result = await manager.set_if_not_exists("new_key", {"data": "value"})

        assert result is True

        # Verify NX flag was set
        call_args = mock_redis.set.call_args
        assert call_args[1]["nx"] is True


class TestCacheStampedeProtection:
    """Tests for cache stampede protection using distributed locks."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        redis = AsyncMock()
        return redis

    @pytest.mark.asyncio
    async def test_acquire_lock_success(self, mock_redis):
        """Test successfully acquiring a lock."""
        mock_redis.set = AsyncMock(return_value=True)

        manager = CacheManager(redis_url="redis://localhost:6379/1")
        manager.redis = mock_redis

        acquired = await manager.acquire_lock("lock:key1", ttl_seconds=30)

        assert acquired is True
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_acquire_lock_failure(self, mock_redis):
        """Test failing to acquire a lock (already held)."""
        mock_redis.set = AsyncMock(return_value=None)

        manager = CacheManager(redis_url="redis://localhost:6379/1")
        manager.redis = mock_redis

        acquired = await manager.acquire_lock("lock:key1", ttl_seconds=30)

        assert acquired is False

    @pytest.mark.asyncio
    async def test_release_lock(self, mock_redis):
        """Test releasing a lock."""
        mock_redis.delete = AsyncMock(return_value=1)

        manager = CacheManager(redis_url="redis://localhost:6379/1")
        manager.redis = mock_redis

        released = await manager.release_lock("lock:key1")

        assert released is True

    @pytest.mark.asyncio
    async def test_lock_expires_after_ttl(self, mock_redis):
        """Test that lock expires after TTL."""
        mock_redis.set = AsyncMock(return_value=True)

        manager = CacheManager(redis_url="redis://localhost:6379/1")
        manager.redis = mock_redis

        await manager.acquire_lock("lock:key1", ttl_seconds=30)

        # Verify EX parameter was set for TTL
        call_args = mock_redis.set.call_args
        assert call_args[1]["ex"] == 30


class TestCacheKeyGeneration:
    """Tests for cache key generation utilities."""

    def test_generate_cache_key_simple(self):
        """Test generating a simple cache key."""
        manager = CacheManager(redis_url="redis://localhost:6379/1")

        key = manager.generate_cache_key("abc123")
        assert key == "youtube:subtitle:abc123"

    def test_generate_cache_key_with_suffix(self):
        """Test generating a cache key with language suffix."""
        manager = CacheManager(redis_url="redis://localhost:6379/1")

        key = manager.generate_cache_key("abc123", suffix="en")
        assert key == "youtube:subtitle:abc123:en"

    def test_generate_cache_key_with_hans_suffix(self):
        """Test generating a cache key with Chinese language suffix."""
        manager = CacheManager(redis_url="redis://localhost:6379/1")

        key = manager.generate_cache_key("abc123", suffix="zh-Hans")
        assert key == "youtube:subtitle:abc123:zh-Hans"

    def test_generate_rate_limit_key(self):
        """Test generating a rate limit tracking key."""
        manager = CacheManager(redis_url="redis://localhost:6379/1")

        key = manager.generate_rate_limit_key("192.168.1.100", "/api/v1/subtitles")
        assert key.startswith("ratelimit:192.168.1.100:")
        # Should contain MD5 hash of endpoint
        assert len(key.split(":")[-1]) == 8


class TestCacheErrorHandling:
    """Tests for cache error handling and resilience."""

    @pytest.mark.asyncio
    async def test_get_handles_connection_error(self):
        """Test that get handles Redis connection errors gracefully."""
        import redis.asyncio as redis
        from redis.exceptions import ConnectionError

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=ConnectionError("Connection lost"))

        manager = CacheManager(redis_url="redis://localhost:6379/1")
        manager.redis = mock_redis

        result = await manager.get("test_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_set_handles_connection_error(self):
        """Test that set handles Redis connection errors gracefully."""
        from redis.exceptions import ConnectionError

        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(side_effect=ConnectionError("Connection lost"))

        manager = CacheManager(redis_url="redis://localhost:6379/1")
        manager.redis = mock_redis

        # Should not raise, just log and return
        await manager.set("test_key", {"data": "value"})

    @pytest.mark.asyncio
    async def test_get_many_handles_partial_results(self, mock_redis):
        """Test that get_many handles partial results correctly."""
        mock_redis.mget = AsyncMock(
            side_effect=ConnectionError("Connection lost")
        )

        manager = CacheManager(redis_url="redis://localhost:6379/1")
        manager.redis = mock_redis

        result = await manager.get_many(["key1", "key2"])

        # Should return empty dict on error
        assert result == {}

    @pytest.mark.asyncio
    async def test_no_redis_client(self):
        """Test behavior when Redis client is None."""
        manager = CacheManager(redis_url="redis://localhost:6379/1")
        manager.redis = None

        result = await manager.get("test_key")
        assert result is None

        await manager.set("test_key", {"data": "value"})  # Should not raise
        deleted = await manager.delete("test_key")
        assert deleted is False


class TestMultiTierCacheStrategy:
    """Tests for multi-tier cache strategy integration."""

    @pytest.mark.asyncio
    async def test_memory_cache_fallback_to_redis(self):
        """Test falling back from memory to Redis cache."""
        memory_cache = InMemoryCache(maxsize=100, ttl_seconds=60)

        # Memory miss
        result1 = await memory_cache.get("key1")
        assert result1 is None

        # Simulate Redis hit
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(
            return_value=json.dumps({"data": "from_redis"})
        )

        manager = CacheManager(redis_url="redis://localhost:6379/1")
        manager.redis = mock_redis

        redis_result = await manager.get("key1")
        assert redis_result == {"data": "from_redis"}

        # Populate memory cache
        await memory_cache.set("key1", redis_result)

        # Now memory hit
        result2 = await memory_cache.get("key1")
        assert result2 == {"data": "from_redis"}

    @pytest.mark.asyncio
    async def test_cache_coherency_between_tiers(self):
        """Test that data remains coherent across cache tiers."""
        memory_cache = InMemoryCache(maxsize=100, ttl_seconds=60)
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(return_value=True)

        manager = CacheManager(redis_url="redis://localhost:6379/1")
        manager.redis = mock_redis

        # Store in both tiers
        data = {"video_id": "abc123", "title": "Test"}
        await memory_cache.set("key1", data)
        await manager.set("key1", data, ttl_seconds=3600)

        # Both should return same data
        memory_data = await memory_cache.get("key1")
        redis_data = await manager.get("key1")

        assert memory_data == redis_data
