"""
Webhook delivery service for async job completion notifications.

Implements:
- HTTP POST delivery to registered webhook URLs
- Exponential backoff retry (3 attempts)
- HMAC signature verification
- Comprehensive error handling
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WebhookPayload:
    """Structured payload for webhook notifications."""

    event: str
    job_id: str
    video_id: str
    status: str
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        payload = {
            "event": self.event,
            "job_id": self.job_id,
            "video_id": self.video_id,
            "status": self.status,
            "timestamp": self.timestamp,
        }
        if self.result is not None:
            payload["result"] = self.result
        if self.error is not None:
            payload["error"] = self.error
        return payload


@dataclass(frozen=True)
class WebhookDeliveryResult:
    """Result of a webhook delivery attempt."""

    success: bool
    status_code: Optional[int] = None
    error: Optional[str] = None
    attempt: int = 1


class WebhookDeliveryError(Exception):
    """Base exception for webhook delivery errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class InvalidWebhookUrlError(WebhookDeliveryError):
    """Raised when webhook URL is invalid."""


class WebhookClient:
    """
    HTTP client for delivering webhook notifications.

    Features:
    - Exponential backoff retry (3 attempts)
    - HMAC signature headers
    - Timeout protection
    - Graceful error handling
    """

    # Maximum retries for webhook delivery
    MAX_RETRIES = 3

    # Base backoff time in seconds
    BASE_BACKOFF = 1.0

    # Maximum backoff time in seconds
    MAX_BACKOFF = 10.0

    # Request timeout in seconds
    REQUEST_TIMEOUT = 10.0

    # Signature header name
    SIGNATURE_HEADER = "X-Webhook-Signature"

    # Timestamp header name
    TIMESTAMP_HEADER = "X-Webhook-Timestamp"

    def __init__(self, webhook_secret: Optional[str] = None):
        """
        Initialize webhook client.

        Args:
            webhook_secret: Secret key for HMAC signature generation.
                           If None, signatures are disabled.
        """
        self.webhook_secret = webhook_secret or settings.WEBHOOK_SECRET
        self._client: Optional[httpx.AsyncClient] = None
        self._client_sync: Optional[httpx.Client] = None

    async def _get_async_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.REQUEST_TIMEOUT,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._client

    def _get_sync_client(self) -> httpx.Client:
        """Get or create sync HTTP client."""
        if self._client_sync is None or self._client_sync.is_closed:
            self._client_sync = httpx.Client(
                timeout=self.REQUEST_TIMEOUT,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._client_sync

    def _generate_signature(self, payload: dict[str, Any], timestamp: str) -> Optional[str]:
        """
        Generate HMAC signature for webhook payload.

        Args:
            payload: The payload to sign
            timestamp: ISO timestamp string for signature

        Returns:
            Hex-encoded HMAC signature, or None if no secret configured
        """
        if not self.webhook_secret:
            return None

        import json

        # Create a canonical payload representation
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))

        # Sign payload + timestamp for freshness
        message = f"{payload_json}.{timestamp}"
        signature = hmac.new(
            self.webhook_secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

        return f"sha256={signature}"

    def _validate_webhook_url(self, url: str) -> None:
        """
        Validate webhook URL format.

        Args:
            url: The webhook URL to validate

        Raises:
            InvalidWebhookUrlError: If URL is invalid
        """
        if not url:
            raise InvalidWebhookUrlError("Webhook URL cannot be empty")

        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
            if not parsed.scheme or parsed.scheme not in ("http", "https"):
                raise InvalidWebhookUrlError(
                    f"Invalid webhook URL scheme: {parsed.scheme}. Only http and https are allowed."
                )
            if not parsed.netloc:
                raise InvalidWebhookUrlError("Webhook URL must have a network location")
        except Exception as e:
            if isinstance(e, InvalidWebhookUrlError):
                raise
            raise InvalidWebhookUrlError(f"Invalid webhook URL format: {e}")

    async def send_async(
        self,
        webhook_url: str,
        payload: WebhookPayload,
    ) -> WebhookDeliveryResult:
        """
        Send webhook notification asynchronously with retry logic.

        Args:
            webhook_url: The URL to send the webhook to
            payload: The webhook payload to send

        Returns:
            WebhookDeliveryResult indicating success or failure
        """
        self._validate_webhook_url(webhook_url)

        from src.core.time_utils import utc_now_iso_z

        # Ensure timestamp is set
        if not payload.timestamp:
            payload = WebhookPayload(
                event=payload.event,
                job_id=payload.job_id,
                video_id=payload.video_id,
                status=payload.status,
                result=payload.result,
                error=payload.error,
                timestamp=utc_now_iso_z(),
            )

        payload_dict = payload.to_dict()
        signature = self._generate_signature(payload_dict, payload.timestamp or "")

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "YouTube-Subtitle-API/1.0",
            self.TIMESTAMP_HEADER: payload.timestamp or "",
        }

        if signature:
            headers[self.SIGNATURE_HEADER] = signature

        last_error = None
        last_status_code = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                client = await self._get_async_client()

                response = await client.post(
                    webhook_url,
                    json=payload_dict,
                    headers=headers,
                )

                last_status_code = response.status_code

                # Accept 2xx status codes
                if 200 <= response.status_code < 300:
                    logger.info(
                        "webhook_delivered",
                        extra={
                            "webhook_url": webhook_url,
                            "job_id": payload.job_id,
                            "status_code": response.status_code,
                            "attempt": attempt,
                        },
                    )
                    return WebhookDeliveryResult(
                        success=True,
                        status_code=response.status_code,
                        attempt=attempt,
                    )

                # Non-2xx response - log and retry
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.warning(
                    "webhook_failed_non_2xx",
                    extra={
                        "webhook_url": webhook_url,
                        "job_id": payload.job_id,
                        "status_code": response.status_code,
                        "attempt": attempt,
                        "response": response.text[:200],
                    },
                )

            except httpx.TimeoutException as e:
                last_error = f"Request timeout: {e}"
                logger.warning(
                    "webhook_timeout",
                    extra={
                        "webhook_url": webhook_url,
                        "job_id": payload.job_id,
                        "attempt": attempt,
                    },
                )

            except httpx.ConnectError as e:
                last_error = f"Connection error: {e}"
                logger.warning(
                    "webhook_connect_error",
                    extra={
                        "webhook_url": webhook_url,
                        "job_id": payload.job_id,
                        "attempt": attempt,
                        "error": str(e),
                    },
                )

            except Exception as e:
                last_error = f"Unexpected error: {e}"
                logger.exception(
                    "webhook_unexpected_error",
                    extra={
                        "webhook_url": webhook_url,
                        "job_id": payload.job_id,
                        "attempt": attempt,
                    },
                )

            # Don't sleep after the last attempt
            if attempt < self.MAX_RETRIES:
                backoff = min(
                    self.BASE_BACKOFF * (2 ** (attempt - 1)),
                    self.MAX_BACKOFF,
                )
                logger.info(
                    "webhook_retry_backoff",
                    extra={
                        "webhook_url": webhook_url,
                        "job_id": payload.job_id,
                        "attempt": attempt,
                        "next_attempt": attempt + 1,
                        "backoff_seconds": backoff,
                    },
                )
                await self._async_sleep(backoff)

        logger.error(
            "webhook_delivery_failed",
            extra={
                "webhook_url": webhook_url,
                "job_id": payload.job_id,
                "attempts": self.MAX_RETRIES,
                "last_error": last_error,
                "last_status_code": last_status_code,
            },
        )

        return WebhookDeliveryResult(
            success=False,
            status_code=last_status_code,
            error=last_error,
            attempt=self.MAX_RETRIES,
        )

    async def _async_sleep(self, seconds: float) -> None:
        """Async sleep for backoff."""
        import anyio

        await anyio.sleep(seconds)

    def send(
        self,
        webhook_url: str,
        payload: WebhookPayload,
    ) -> WebhookDeliveryResult:
        """
        Send webhook notification synchronously with retry logic.

        This is a wrapper around send_async for use in sync contexts
        (e.g., RQ worker tasks). It runs the async code in a new event loop.

        Args:
            webhook_url: The URL to send the webhook to
            payload: The webhook payload to send

        Returns:
            WebhookDeliveryResult indicating success or failure
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("Event loop is closed")
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.send_async(webhook_url, payload))

    async def close(self) -> None:
        """Close HTTP clients."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def close_sync(self) -> None:
        """Close sync HTTP client."""
        if self._client_sync and not self._client_sync.is_closed:
            self._client_sync.close()
            self._client_sync = None


# Singleton instance factory
_client_instance: Optional[WebhookClient] = None


def get_webhook_client() -> WebhookClient:
    """Get singleton webhook client instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = WebhookClient()
    return _client_instance


async def send_webhook(
    webhook_url: str,
    job_id: str,
    video_id: str,
    status: str,
    result: Optional[dict[str, Any]] = None,
    error: Optional[str] = None,
) -> WebhookDeliveryResult:
    """
    Convenience function to send a webhook notification.

    Args:
        webhook_url: The URL to send the webhook to
        job_id: The job ID
        video_id: The video ID
        status: The job status (success, failed, etc.)
        result: Optional result data for successful jobs
        error: Optional error message for failed jobs

    Returns:
        WebhookDeliveryResult indicating success or failure
    """
    from src.core.time_utils import utc_now_iso_z

    payload = WebhookPayload(
        event="job.completed",
        job_id=job_id,
        video_id=video_id,
        status=status,
        result=result,
        error=error,
        timestamp=utc_now_iso_z(),
    )

    client = get_webhook_client()
    return await client.send_async(webhook_url, payload)


def send_webhook_sync(
    webhook_url: str,
    job_id: str,
    video_id: str,
    status: str,
    result: Optional[dict[str, Any]] = None,
    error: Optional[str] = None,
) -> WebhookDeliveryResult:
    """
    Convenience function to send a webhook notification synchronously.

    This is intended for use in RQ worker tasks.

    Args:
        webhook_url: The URL to send the webhook to
        job_id: The job ID
        video_id: The video ID
        status: The job status (success, failed, etc.)
        result: Optional result data for successful jobs
        error: Optional error message for failed jobs

    Returns:
        WebhookDeliveryResult indicating success or failure
    """
    from src.core.time_utils import utc_now_iso_z

    payload = WebhookPayload(
        event="job.completed",
        job_id=job_id,
        video_id=video_id,
        status=status,
        result=result,
        error=error,
        timestamp=utc_now_iso_z(),
    )

    client = get_webhook_client()
    return client.send(webhook_url, payload)
