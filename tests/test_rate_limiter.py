from __future__ import annotations

import pytest
import redis.asyncio as redis

from src.services.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_blocks_after_capacity():
    client = redis.Redis.from_url("redis://redis:6379/2", decode_responses=True)
    await client.flushdb()

    limiter = RateLimiter(redis_client=client, requests_per_minute=2, burst_size=0)

    allowed1, _, _ = await limiter.check_rate_limit("1.2.3.4", "/api/rewrite-video")
    allowed2, _, _ = await limiter.check_rate_limit("1.2.3.4", "/api/rewrite-video")
    allowed3, _, _ = await limiter.check_rate_limit("1.2.3.4", "/api/rewrite-video")

    assert allowed1 is True
    assert allowed2 is True
    assert allowed3 is False

    aclose = getattr(client, "aclose", None)
    if callable(aclose):
        await aclose()
    else:
        await client.close()
