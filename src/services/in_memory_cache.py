from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Optional

from cachetools import TTLCache


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total) if total else 0.0


class InMemoryCache:
    """
    Small hot-cache (Tier 1).

    Designed for the API process only; use Redis/PostgreSQL for persistence.
    """

    def __init__(self, maxsize: int, ttl_seconds: int):
        self._cache: TTLCache[str, Any] = TTLCache(maxsize=maxsize, ttl=ttl_seconds)
        self._lock = asyncio.Lock()
        self.stats = CacheStats()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            value = self._cache.get(key)
            if value is None:
                self.stats.misses += 1
                return None
            self.stats.hits += 1
            return value

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        """
        Get multiple values from cache in a single lock acquisition.

        PERFORMANCE: Acquires the lock once instead of N times, reducing
        contention in high-concurrency scenarios.
        """
        async with self._lock:
            result = {}
            for key in keys:
                value = self._cache.get(key)
                if value is not None:
                    result[key] = value
                    self.stats.hits += 1
                else:
                    self.stats.misses += 1
            return result

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            self._cache[key] = value

    async def delete(self, key: str) -> bool:
        async with self._lock:
            existed = key in self._cache
            self._cache.pop(key, None)
            return existed

    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()

    async def size(self) -> int:
        async with self._lock:
            return len(self._cache)
