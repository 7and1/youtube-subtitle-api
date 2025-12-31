"""
Rate limiting implementation using token bucket algorithm in Redis.

SECURITY POLICY:
- Fails CLOSED when Redis is unavailable (deny requests)
- All rate limit errors are logged for security monitoring
- Configurable fail-open mode for development (not recommended for production)
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Tuple, Optional
from dataclasses import dataclass

from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.core.config import settings
from src.core.time_utils import utc_now

logger = logging.getLogger(__name__)


@dataclass
class RateLimitInfo:
    """Rate limit information for response headers."""

    limit: int
    remaining: int
    reset_at: float  # Unix timestamp


class RateLimiter:
    """
    Token bucket rate limiter using Redis.

    SECURITY: This rate limiter FAILS CLOSED by default. If Redis is unavailable,
    all requests will be denied. This prevents abuse during infrastructure failures.

    To enable fail-open mode (DANGEROUS, not recommended for production):
    - Set RATE_LIMIT_FAIL_OPEN=true in environment
    """

    # Connection check threshold - log connection errors at most once per this interval
    CONNECTION_ERROR_LOG_INTERVAL = 60  # seconds
    _last_connection_error_log = 0

    def __init__(
        self,
        redis_client: Redis,
        requests_per_minute: int = 30,
        burst_size: int = 5,
        fail_open: bool = False,
    ):
        """
        Initialize rate limiter.

        Args:
            redis_client: Async Redis client instance
            requests_per_minute: Base rate limit
            burst_size: Additional burst capacity
            fail_open: If True, allow requests when Redis fails (DANGEROUS).
                       Defaults to False for security. Override via env var
                       RATE_LIMIT_FAIL_OPEN=true if absolutely necessary.
        """
        self.redis = redis_client
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.capacity = requests_per_minute + burst_size
        self.refill_per_second = requests_per_minute / 60.0
        self.fail_open = fail_open

        # Atomic token bucket (stores tokens + last timestamp)
        self._lua = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local refill_per_second = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])
local ttl = tonumber(ARGV[5])

local data = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(data[1])
local ts = tonumber(data[2])

if tokens == nil or ts == nil then
  tokens = capacity
  ts = now
end

local delta = now - ts
if delta < 0 then delta = 0 end
tokens = math.min(capacity, tokens + (delta * refill_per_second))

local allowed = 0
if tokens >= cost then
  allowed = 1
  tokens = tokens - cost
end

redis.call('HSET', key, 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', key, ttl)

return {allowed, tokens}
"""

    @classmethod
    def from_settings(cls, redis_client: Redis) -> "RateLimiter":
        """
        Create RateLimiter instance from application settings.

        Reads RATE_LIMIT_FAIL_OPEN from environment to determine fail-open behavior.
        """
        fail_open = getattr(settings, "RATE_LIMIT_FAIL_OPEN", False)
        if isinstance(fail_open, str):
            fail_open = fail_open.lower() in ("true", "1", "yes", "on")

        return cls(
            redis_client=redis_client,
            requests_per_minute=getattr(settings, "RATE_LIMIT_REQUESTS_PER_MINUTE", 30),
            burst_size=getattr(settings, "RATE_LIMIT_BURST_SIZE", 5),
            fail_open=fail_open,
        )

    def _should_log_connection_error(self) -> bool:
        """Rate limit connection error logging to avoid log spam."""
        now = time.time()
        if now - RateLimiter._last_connection_error_log >= self.CONNECTION_ERROR_LOG_INTERVAL:
            RateLimiter._last_connection_error_log = now
            return True
        return False

    async def check_rate_limit(
        self,
        client_ip: str,
        endpoint: str,
    ) -> Tuple[bool, int, datetime, Optional[RateLimitInfo]]:
        """
        Check if request is allowed under rate limit.

        SECURITY: When Redis is unavailable, this FAILS CLOSED by default,
        denying all requests. Set RATE_LIMIT_FAIL_OPEN=true to override
        (not recommended for production).

        Returns:
            Tuple[allowed, remaining_requests, reset_at, rate_limit_info]
        """
        # Keep keys compact to avoid unbounded cardinality from long URLs.
        import hashlib

        endpoint_hash = hashlib.md5(endpoint.encode("utf-8")).hexdigest()[:8]
        key = f"ratelimit:{client_ip}:{endpoint_hash}"

        try:
            now = time.time()
            # redis-py `eval` expects positional args: (script, numkeys, *keys_and_args)
            allowed, tokens = await self.redis.eval(
                self._lua,
                1,
                key,
                now,
                self.capacity,
                self.refill_per_second,
                1,
                61,
            )
            tokens_int = int(tokens)
            reset_at_timestamp = now + 61

            if int(allowed) == 1:
                reset_at = utc_now() + timedelta(seconds=61)
                info = RateLimitInfo(
                    limit=self.requests_per_minute,
                    remaining=tokens_int,
                    reset_at=reset_at_timestamp,
                )
                return True, tokens_int, reset_at, info

            # Estimate time until next token is available.
            wait_seconds = max(1.0 / max(self.refill_per_second, 1e-6), 1.0)
            reset_at = utc_now() + timedelta(seconds=wait_seconds)
            reset_at_timestamp = now + wait_seconds
            info = RateLimitInfo(
                limit=self.requests_per_minute,
                remaining=0,
                reset_at=reset_at_timestamp,
            )
            return False, 0, reset_at, info

        except RedisError as e:
            # SECURITY: Log the error with appropriate severity
            if self._should_log_connection_error():
                log_level = logging.WARNING if self.fail_open else logging.ERROR
                logger.log(
                    log_level,
                    "rate_limit_redis_error",
                    extra={
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "fail_open_mode": self.fail_open,
                        "client_ip": client_ip[:16],  # Truncated for privacy
                    },
                )

            # SECURITY POLICY: Fail CLOSED by default
            if self.fail_open:
                # DANGEROUS: Only enable if absolutely necessary for availability
                logger.warning(
                    "rate_limit_fail_open_enabled",
                    extra={"reason": "Redis unavailable, fail-open mode active"},
                )
                reset_at = utc_now() + timedelta(minutes=1)
                info = RateLimitInfo(
                    limit=self.requests_per_minute,
                    remaining=self.requests_per_minute,
                    reset_at=time.time() + 60,
                )
                return (
                    True,
                    self.requests_per_minute,
                    reset_at,
                    info,
                )
            else:
                # SECURE DEFAULT: Deny request when Redis is unavailable
                # This prevents abuse during infrastructure failures
                reset_at = utc_now() + timedelta(seconds=60)
                info = RateLimitInfo(
                    limit=self.requests_per_minute,
                    remaining=0,
                    reset_at=time.time() + 60,
                )
                return False, 0, reset_at, info

        except Exception as e:
            # Catch-all for unexpected errors
            logger.error(
                "rate_limit_unexpected_error",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "client_ip": client_ip[:16],
                },
            )
            # SECURITY: Fail closed on unexpected errors too
            reset_at = utc_now() + timedelta(seconds=60)
            info = RateLimitInfo(
                limit=self.requests_per_minute,
                remaining=0,
                reset_at=time.time() + 60,
            )
            return False, 0, reset_at, info

    async def reset_for_client(self, client_ip: str):
        """Reset rate limit for specific client."""
        try:
            pattern = f"ratelimit:{client_ip}:*"
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
                    "rate_limit_reset",
                    extra={"client_ip": client_ip, "deleted": deleted},
                )
        except Exception as e:
            logger.error(f"Rate limit reset error: {e}")

    async def get_stats(self, client_ip: str) -> dict:
        """Get rate limit stats for client."""
        try:
            keys: list[str] = []
            async for key in self.redis.scan_iter(
                match=f"ratelimit:{client_ip}:*", count=500
            ):
                keys.append(key)
                if len(keys) >= 500:
                    break
            stats = {}

            for key in keys:
                endpoint = key.split(":")[-1]
                tokens = await self.redis.hget(key, "tokens")
                ttl = await self.redis.ttl(key)
                stats[endpoint] = {
                    "remaining": int(float(tokens)) if tokens else 0,
                    "reset_in_seconds": max(ttl, 0),
                }

            return stats
        except Exception as e:
            logger.error(f"Rate limit stats error: {e}")
            return {}
