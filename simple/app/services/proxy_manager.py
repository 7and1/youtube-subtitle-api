"""
Proxy rotation manager for YouTube subtitle extraction.
Supports multiple proxy formats and automatic failover.
"""
import os
import random
import time
from dataclasses import dataclass
from typing import Optional, List
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

PROXY_FILE_PATH = os.getenv("PROXY_FILE_PATH", "/app/config/proxies.txt")
PROXY_COOLDOWN_SECONDS = int(os.getenv("PROXY_COOLDOWN_SECONDS", "60"))
PROXY_MAX_FAILURES = int(os.getenv("PROXY_MAX_FAILURES", "3"))


@dataclass
class Proxy:
    """Proxy configuration."""
    host: str
    port: int
    username: str
    password: str
    failures: int = 0
    last_used: float = 0
    last_failure: float = 0

    @property
    def url(self) -> str:
        """Return proxy URL in format http://user:pass@host:port"""
        return f"http://{self.username}:{self.password}@{self.host}:{self.port}"

    @property
    def url_dict(self) -> dict:
        """Return proxy dict for requests/httpx."""
        return {
            "http": self.url,
            "https": self.url
        }

    def is_available(self) -> bool:
        """Check if proxy is available (not in cooldown)."""
        if self.failures >= PROXY_MAX_FAILURES:
            # Check if cooldown period has passed
            if time.time() - self.last_failure > PROXY_COOLDOWN_SECONDS * self.failures:
                self.failures = 0  # Reset after extended cooldown
                return True
            return False
        return True


class ProxyManager:
    """
    Manages proxy rotation with failure tracking.

    Features:
    - Automatic proxy rotation
    - Failure tracking and cooldown
    - Health monitoring
    - Random selection to distribute load
    """

    def __init__(self, proxy_file: Optional[str] = None):
        self.proxy_file = proxy_file or PROXY_FILE_PATH
        self.proxies: List[Proxy] = []
        self.current_index: int = 0
        self._load_proxies()

    def _load_proxies(self) -> None:
        """Load proxies from file."""
        proxy_path = Path(self.proxy_file)

        if not proxy_path.exists():
            logger.warning("proxy_file_not_found", path=self.proxy_file)
            return

        try:
            with open(proxy_path, 'r') as f:
                lines = f.readlines()

            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                proxy = self._parse_proxy_line(line)
                if proxy:
                    self.proxies.append(proxy)

            logger.info("proxies_loaded", count=len(self.proxies))

        except Exception as e:
            logger.error("proxy_load_error", error=str(e))

    def _parse_proxy_line(self, line: str) -> Optional[Proxy]:
        """
        Parse proxy line in supported formats:
        - ip:port,user,pass
        - ip:port:user:pass
        """
        try:
            # Format 1: ip:port,user,pass
            if ',' in line:
                parts = line.split(',')
                if len(parts) >= 3:
                    host_port = parts[0].split(':')
                    return Proxy(
                        host=host_port[0],
                        port=int(host_port[1]),
                        username=parts[1],
                        password=parts[2]
                    )

            # Format 2: ip:port:user:pass
            parts = line.split(':')
            if len(parts) >= 4:
                return Proxy(
                    host=parts[0],
                    port=int(parts[1]),
                    username=parts[2],
                    password=parts[3]
                )

        except Exception as e:
            logger.warning("proxy_parse_error", line=line[:30], error=str(e))

        return None

    def get_proxy(self) -> Optional[Proxy]:
        """Get next available proxy using round-robin with health check."""
        if not self.proxies:
            return None

        available = [p for p in self.proxies if p.is_available()]

        if not available:
            logger.warning("no_proxies_available", total=len(self.proxies))
            # Reset all proxies if none available
            for p in self.proxies:
                p.failures = 0
            available = self.proxies

        # Random selection to distribute load
        proxy = random.choice(available)
        proxy.last_used = time.time()

        return proxy

    def get_random_proxy(self) -> Optional[Proxy]:
        """Get a random available proxy."""
        return self.get_proxy()

    def mark_success(self, proxy: Proxy) -> None:
        """Mark proxy as successful, reset failure count."""
        proxy.failures = 0
        logger.debug("proxy_success", host=proxy.host, port=proxy.port)

    def mark_failure(self, proxy: Proxy, error: str = "") -> None:
        """Mark proxy as failed, increment failure count."""
        proxy.failures += 1
        proxy.last_failure = time.time()
        logger.warning("proxy_failure",
                      host=proxy.host,
                      port=proxy.port,
                      failures=proxy.failures,
                      error=error[:100])

    def get_stats(self) -> dict:
        """Get proxy pool statistics."""
        available = sum(1 for p in self.proxies if p.is_available())
        return {
            "total": len(self.proxies),
            "available": available,
            "unavailable": len(self.proxies) - available,
            "failure_rate": 1 - (available / len(self.proxies)) if self.proxies else 0
        }

    @property
    def has_proxies(self) -> bool:
        """Check if any proxies are loaded."""
        return len(self.proxies) > 0


# Singleton instance
_proxy_manager: Optional[ProxyManager] = None


def get_proxy_manager() -> ProxyManager:
    """Get or create proxy manager singleton."""
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = ProxyManager()
    return _proxy_manager
