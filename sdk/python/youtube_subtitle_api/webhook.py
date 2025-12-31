"""
Webhook utilities for the YouTube Subtitle API SDK.

This module provides functions for verifying webhook signatures
and parsing webhook payloads.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Optional

from .models import WebhookEvent


def verify_signature(
    payload: bytes | str,
    signature: str,
    secret: str,
    timestamp: Optional[str] = None,
) -> bool:
    """
    Verify the HMAC signature of a webhook payload.

    The API signs webhooks using HMAC-SHA256. The signature is computed
    from the payload JSON plus an optional timestamp for freshness.

    Args:
        payload: The raw webhook payload (bytes or string)
        signature: The X-Webhook-Signature header value (e.g., "sha256=abc...")
        secret: Your webhook secret key
        timestamp: Optional X-Webhook-Timestamp header value

    Returns:
        True if signature is valid, False otherwise

    Example:
        >>> from fastapi import Request
        >>>
        >>> @app.post("/webhook")
        >>> async def handle_webhook(request: Request):
        ...     payload = await request.body()
        ...     sig = request.headers.get("X-Webhook-Signature", "")
        ...     ts = request.headers.get("X-Webhook-Timestamp", "")
        ...
        ...     if not verify_signature(payload, sig, WEBHOOK_SECRET, ts):
        ...         raise HTTPException(status_code=401, detail="Invalid signature")
        ...
        ...     event = parse_webhook(payload)
        ...     return {"status": "received"}
    """
    # Extract signature hash (remove "sha256=" prefix if present)
    if signature.startswith("sha256="):
        signature_hash = signature[7:]
    else:
        signature_hash = signature

    # Ensure payload is bytes for consistent hashing
    if isinstance(payload, str):
        payload_bytes = payload.encode("utf-8")
    else:
        payload_bytes = payload

    # Create the message to sign
    # The API signs: payload_json + "." + timestamp
    if timestamp:
        message = f"{payload_bytes.decode('utf-8')}.{timestamp}"
    else:
        message = payload_bytes.decode("utf-8")

    # Compute expected signature
    expected_hash = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(signature_hash, expected_hash)


def parse_webhook(payload: bytes | str | dict[str, Any]) -> WebhookEvent:
    """
    Parse a webhook payload into a WebhookEvent object.

    Args:
        payload: The webhook payload (bytes, string, or dict)

    Returns:
        WebhookEvent object with the parsed data

    Raises:
        ValueError: If payload is invalid

    Example:
        >>> @app.post("/webhook")
        >>> async def handle_webhook(request: Request):
        ...     payload = await request.body()
        ...     event = parse_webhook(payload)
        ...
        ...     if event.is_success:
        ...         subtitle = event.subtitle
        ...         print(f"Got {len(subtitle.subtitles)} subtitle items")
        ...     else:
        ...         print(f"Job failed: {event.error}")
    """
    # Parse JSON if needed
    if isinstance(payload, dict):
        data = payload
    elif isinstance(payload, bytes):
        data = json.loads(payload.decode("utf-8"))
    elif isinstance(payload, str):
        data = json.loads(payload)
    else:
        raise ValueError(f"Invalid payload type: {type(payload)}")

    return WebhookEvent.from_dict(data)


def verify_and_parse_webhook(
    payload: bytes | str,
    signature: str,
    secret: str,
    timestamp: Optional[str] = None,
) -> WebhookEvent:
    """
    Verify signature and parse webhook payload in one step.

    This is a convenience function that combines verify_signature()
    and parse_webhook().

    Args:
        payload: The raw webhook payload
        signature: The X-Webhook-Signature header value
        secret: Your webhook secret key
        timestamp: Optional X-Webhook-Timestamp header value

    Returns:
        WebhookEvent object with the parsed data

    Raises:
        ValueError: If signature is invalid or payload cannot be parsed

    Example:
        >>> @app.post("/webhook")
        >>> async def handle_webhook(request: Request):
        ...     payload = await request.body()
        ...     sig = request.headers.get("X-Webhook-Signature", "")
        ...     ts = request.headers.get("X-Webhook-Timestamp", "")
        ...
        ...     try:
        ...         event = verify_and_parse_webhook(payload, sig, WEBHOOK_SECRET, ts)
        ...     except ValueError:
        ...         raise HTTPException(status_code=401, detail="Invalid signature")
        ...
        ...     return process_event(event)
    """
    if not verify_signature(payload, signature, secret, timestamp):
        raise ValueError("Invalid webhook signature")

    return parse_webhook(payload)


def generate_signature(
    payload: dict[str, Any] | str,
    secret: str,
    timestamp: Optional[str] = None,
) -> str:
    """
    Generate an HMAC signature for a webhook payload.

    This is useful for testing webhook handlers or for making
    signed webhook requests to other services.

    Args:
        payload: The payload to sign (dict or string)
        secret: The webhook secret key
        timestamp: Optional timestamp to include in signature

    Returns:
        The signature hash (without "sha256=" prefix)

    Example:
        >>> payload = {"event": "job.completed", "job_id": "123"}
        >>> sig = generate_signature(payload, "my_secret")
        >>> headers = {"X-Webhook-Signature": f"sha256={sig}"}
    """
    if isinstance(payload, dict):
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    else:
        payload_json = payload

    if timestamp:
        message = f"{payload_json}.{timestamp}"
    else:
        message = payload_json

    signature_hash = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return signature_hash


class WebhookVerifier:
    """
    A reusable webhook verifier with pre-configured secret.

    Example:
        >>> verifier = WebhookVerifier(secret="my_webhook_secret")
        >>>
        >>> @app.post("/webhook")
        >>> async def handle_webhook(request: Request):
        ...     payload = await request.body()
        ...     sig = request.headers.get("X-Webhook-Signature", "")
        ...     ts = request.headers.get("X-Webhook-Timestamp", "")
        ...
        ...     event = verifier.verify_and_parse(payload, sig, ts)
        ...     return {"status": "received"}
    """

    def __init__(self, secret: str, require_timestamp: bool = False):
        """
        Initialize the verifier.

        Args:
            secret: Your webhook secret key
            require_timestamp: Whether to require timestamp in signatures
        """
        self.secret = secret
        self.require_timestamp = require_timestamp

    def verify(
        self,
        payload: bytes | str,
        signature: str,
        timestamp: Optional[str] = None,
    ) -> bool:
        """
        Verify a webhook signature.

        Args:
            payload: The raw webhook payload
            signature: The X-Webhook-Signature header value
            timestamp: Optional X-Webhook-Timestamp header value

        Returns:
            True if signature is valid
        """
        if self.require_timestamp and not timestamp:
            return False

        return verify_signature(payload, signature, self.secret, timestamp)

    def parse(self, payload: bytes | str | dict[str, Any]) -> WebhookEvent:
        """
        Parse a webhook payload.

        Args:
            payload: The webhook payload

        Returns:
            WebhookEvent object
        """
        return parse_webhook(payload)

    def verify_and_parse(
        self,
        payload: bytes | str,
        signature: str,
        timestamp: Optional[str] = None,
    ) -> WebhookEvent:
        """
        Verify signature and parse webhook payload.

        Args:
            payload: The raw webhook payload
            signature: The X-Webhook-Signature header value
            timestamp: Optional X-Webhook-Timestamp header value

        Returns:
            WebhookEvent object

        Raises:
            ValueError: If signature is invalid
        """
        if not self.verify(payload, signature, timestamp):
            raise ValueError("Invalid webhook signature")

        return self.parse(payload)
