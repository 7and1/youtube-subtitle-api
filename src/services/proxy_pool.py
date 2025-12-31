from __future__ import annotations

import hashlib
import random
import time
from dataclasses import dataclass
from typing import Optional

from redis.asyncio import Redis

from src.core.config import settings


@dataclass(frozen=True)
class ProxyChoice:
    url: str

    @property
    def id(self) -> str:
        return hashlib.sha256(self.url.encode("utf-8")).hexdigest()[:16]


def _normalize_proxy_url(url: str) -> str:
    u = url.strip()
    if not u:
        return ""
    if "://" not in u:
        u = f"http://{u}"
    # Inject auth if configured and missing.
    if settings.YT_PROXY_AUTH and "@" not in u and "://" in u:
        scheme, rest = u.split("://", 1)
        u = f"{scheme}://{settings.YT_PROXY_AUTH}@{rest}"
    return u


def _proxy_list() -> list[ProxyChoice]:
    if not settings.YT_PROXY_URLS:
        return []
    urls = [_normalize_proxy_url(u) for u in settings.YT_PROXY_URLS.split(",")]
    urls = [u for u in urls if u]
    return [ProxyChoice(url=u) for u in urls]


async def _is_available(redis: Redis, proxy: ProxyChoice) -> bool:
    fails_key = f"proxy:fails:{proxy.id}"
    last_key = f"proxy:last_failure:{proxy.id}"
    fails_raw = await redis.get(fails_key)
    fails = int(fails_raw) if fails_raw else 0
    if fails < settings.PROXY_MAX_FAILURES:
        return True
    last_raw = await redis.get(last_key)
    last = float(last_raw) if last_raw else 0.0
    cooldown = settings.PROXY_COOLDOWN_SECONDS * max(fails, 1)
    return (time.time() - last) > cooldown


async def choose_proxy(redis: Redis) -> Optional[ProxyChoice]:
    proxies = _proxy_list()
    if not proxies:
        return None
    random.shuffle(proxies)
    for p in proxies:
        if await _is_available(redis, p):
            return p
    # If none available, fail open (allow a random one).
    return random.choice(proxies)


async def mark_proxy_success(redis: Redis, proxy: ProxyChoice) -> None:
    await redis.delete(f"proxy:fails:{proxy.id}")
    await redis.delete(f"proxy:last_failure:{proxy.id}")


async def mark_proxy_failure(redis: Redis, proxy: ProxyChoice) -> None:
    fails_key = f"proxy:fails:{proxy.id}"
    last_key = f"proxy:last_failure:{proxy.id}"
    await redis.incr(fails_key)
    await redis.set(last_key, str(time.time()), ex=24 * 3600)
