"""
YouTube Subtitle API SDK - Python Client

A modern, type-hinted Python SDK for interacting with the YouTube Subtitle API.
Supports both synchronous and asynchronous operations.

Example:
    >>> from youtube_subtitle_api import YouTubeSubtitleAPI
    >>> client = YouTubeSubtitleAPI(api_key="your-key")
    >>> result = client.extract_subtitles("dQw4w9WgXcQ", language="en")
    >>> print(result['plain_text'])
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Union

import httpx

from .errors import (
    APIError,
    AuthenticationError,
    InvalidVideoIDError,
    NotFoundError,
    RateLimitError,
    ValidationError,
    YouTubeSubtitleAPIError,
)
from .models import JobStatus, Subtitle, SubtitleItem, WebhookEvent
from .webhook import verify_signature

__all__ = [
    # Main client
    "YouTubeSubtitleAPI",
    "AsyncYouTubeSubtitleAPI",
    # Configuration
    "Config",
    # Models
    "Subtitle",
    "SubtitleItem",
    "JobStatus",
    "WebhookEvent",
    # Errors
    "YouTubeSubtitleAPIError",
    "APIError",
    "AuthenticationError",
    "RateLimitError",
    "NotFoundError",
    "ValidationError",
    "InvalidVideoIDError",
    # Webhook utilities
    "verify_signature",
]

__version__ = "1.0.0"
__author__ = "YouTube Subtitle API Team"
__license__ = "MIT"

logger = logging.getLogger(__name__)


# Video ID validation pattern
VIDEO_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{11}$")
YOUTUBE_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be)/"
    r"(?:watch\?v=|shorts/)?([a-zA-Z0-9_-]{11})"
)


def extract_video_id(input_str: str) -> str:
    """
    Extract YouTube video ID from URL or validate as video ID.

    Args:
        input_str: YouTube URL or video ID

    Returns:
        The 11-character video ID

    Raises:
        InvalidVideoIDError: If the input is not a valid URL or video ID
    """
    # Direct video ID match
    if VIDEO_ID_PATTERN.match(input_str):
        return input_str

    # URL extraction
    match = YOUTUBE_URL_PATTERN.search(input_str)
    if match:
        return match.group(1)

    raise InvalidVideoIDError(
        f"Invalid YouTube URL or video ID: {input_str}. "
        "Provide a valid 11-character video ID or full YouTube URL."
    )


@dataclass(frozen=True)
class Config:
    """
    SDK configuration.

    Attributes:
        api_key: Optional API key for authenticated requests
        base_url: Base URL of the YouTube Subtitle API
        timeout: Request timeout in seconds
        max_retries: Maximum number of retries for failed requests
        webhook_secret: Secret for verifying webhook signatures
    """

    api_key: Optional[str] = None
    base_url: str = "https://api.expertbeacon.com"
    timeout: float = 30.0
    max_retries: int = 3
    webhook_secret: Optional[str] = None

    def with_api_key(self, api_key: str) -> "Config":
        """Return a new Config with the API key set."""
        return Config(
            api_key=api_key,
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=self.max_retries,
            webhook_secret=self.webhook_secret,
        )


@dataclass
class ExtractionRequest:
    """
    Request parameters for subtitle extraction.

    Attributes:
        video_id: YouTube video ID (11 characters)
        video_url: Full YouTube URL (alternative to video_id)
        language: Subtitle language code (default: "en")
        clean_for_ai: Normalize text for AI consumption (default: True)
        webhook_url: Optional webhook URL for async completion notification
    """

    video_id: Optional[str] = None
    video_url: Optional[str] = None
    language: str = "en"
    clean_for_ai: bool = True
    webhook_url: Optional[str] = None

    def __post_init__(self):
        """Validate and normalize the request."""
        if not self.video_id and not self.video_url:
            raise ValidationError(
                "Either video_id or video_url must be provided"
            )

        # Extract video ID from URL if needed
        if self.video_url and not self.video_id:
            object.__setattr__(self, "video_id", extract_video_id(self.video_url))

        # Validate video ID format
        if self.video_id and not VIDEO_ID_PATTERN.match(self.video_id):
            raise InvalidVideoIDError(
                f"Invalid video ID format: {self.video_id}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to API request dictionary."""
        payload: dict[str, Any] = {
            "language": self.language,
            "clean_for_ai": self.clean_for_ai,
        }

        if self.video_id:
            payload["video_id"] = self.video_id
        if self.webhook_url:
            payload["webhook_url"] = self.webhook_url

        return payload


@dataclass
class BatchExtractionRequest:
    """
    Request parameters for batch subtitle extraction.

    Attributes:
        video_ids: List of YouTube video IDs (up to 100)
        language: Subtitle language code (default: "en")
        clean_for_ai: Normalize text for AI consumption (default: True)
        webhook_url: Optional webhook URL for async completion notifications
    """

    video_ids: list[str]
    language: str = "en"
    clean_for_ai: bool = True
    webhook_url: Optional[str] = None

    def __post_init__(self):
        """Validate the batch request."""
        if not self.video_ids:
            raise ValidationError("video_ids cannot be empty")

        if len(self.video_ids) > 100:
            raise ValidationError("video_ids cannot exceed 100 items")

        # Validate all video IDs
        for vid in self.video_ids:
            if not VIDEO_ID_PATTERN.match(vid):
                raise InvalidVideoIDError(f"Invalid video ID format: {vid}")

    def to_dict(self) -> dict[str, Any]:
        """Convert to API request dictionary."""
        payload: dict[str, Any] = {
            "video_ids": self.video_ids,
            "language": self.language,
            "clean_for_ai": self.clean_for_ai,
        }

        if self.webhook_url:
            payload["webhook_url"] = self.webhook_url

        return payload


@dataclass
class JobInfo:
    """
    Information about an extraction job.

    Attributes:
        job_id: Unique job identifier
        status: Current job status
        enqueued_at: When the job was queued
        ended_at: When the job completed (if finished)
        result: The result data (if completed successfully)
        exc_info: Exception info (if failed)
    """

    job_id: str
    status: Union[str, JobStatus]
    enqueued_at: Optional[str] = None
    ended_at: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    exc_info: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobInfo":
        """Create JobInfo from API response."""
        status_str = data.get("status", "unknown")
        try:
            status = JobStatus(status_str)
        except ValueError:
            status = JobStatus.UNKNOWN

        return cls(
            job_id=data.get("job_id", ""),
            status=status,
            enqueued_at=data.get("enqueued_at"),
            ended_at=data.get("ended_at"),
            result=data.get("result"),
            exc_info=data.get("exc_info"),
        )

    @property
    def is_pending(self) -> bool:
        """Check if job is still pending."""
        return self.status in (JobStatus.QUEUED, JobStatus.STARTED)

    @property
    def is_complete(self) -> bool:
        """Check if job completed successfully."""
        return self.status == JobStatus.FINISHED and self.result is not None

    @property
    def is_failed(self) -> bool:
        """Check if job failed."""
        return self.status == JobStatus.FAILED

    @property
    def subtitle(self) -> Optional[Subtitle]:
        """Get Subtitle object if job completed successfully."""
        if self.is_complete and self.result:
            return Subtitle.from_dict(self.result)
        return None


@dataclass
class BatchExtractionResult:
    """
    Result of a batch extraction request.

    Attributes:
        status: Overall status (always "queued")
        video_count: Total number of videos requested
        queued_count: Number of videos queued for extraction
        cached_count: Number of videos with cached results
        job_ids: List of job IDs for queued extractions
        cached: List of video IDs with cached results
    """

    status: str
    video_count: int
    queued_count: int
    cached_count: int
    job_ids: list[str]
    cached: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BatchExtractionResult":
        """Create BatchExtractionResult from API response."""
        return cls(
            status=data.get("status", "queued"),
            video_count=data.get("video_count", 0),
            queued_count=data.get("queued_count", 0),
            cached_count=data.get("cached_count", 0),
            job_ids=data.get("job_ids", []),
            cached=data.get("cached", []),
        )


@dataclass
class QueuedResponse:
    """
    Response when a subtitle extraction is queued.

    Attributes:
        job_id: Unique job identifier
        status: Always "queued"
        video_id: The YouTube video ID
        language: Requested language
        webhook_url: Webhook URL if provided
    """

    job_id: str
    status: str
    video_id: str
    language: str
    webhook_url: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QueuedResponse":
        """Create QueuedResponse from API response."""
        return cls(
            job_id=data["job_id"],
            status=data["status"],
            video_id=data["video_id"],
            language=data["language"],
            webhook_url=data.get("webhook_url"),
        )


def _parse_error_response(status_code: int, data: dict[str, Any]) -> YouTubeSubtitleAPIError:
    """
    Parse an API error response into an appropriate exception.

    Args:
        status_code: HTTP status code
        data: Response JSON data

    Returns:
        Appropriate exception instance
    """
    error = data.get("error", {})
    error_code = error.get("code", "")
    message = error.get("message", "")
    hint = error.get("hint", "")

    # Map error codes to exceptions
    if error_code == "RATE_LIMIT_EXCEEDED" or status_code == 429:
        return RateLimitError(message=message, hint=hint)
    if error_code == "UNAUTHORIZED" or status_code == 401:
        return AuthenticationError(message=message, hint=hint)
    if error_code == "SUBTITLE_NOT_FOUND" or status_code == 404:
        return NotFoundError(message=message, hint=hint)
    if error_code == "INVALID_VIDEO_ID" or error_code == "INVALID_REQUEST":
        return ValidationError(message=message, hint=hint)

    # Generic API error
    return APIError(message=message or f"HTTP {status_code}", status_code=status_code)


class _BaseClient:
    """
    Base client with shared HTTP functionality.
    """

    def __init__(self, config: Config):
        self.config = config
        self._base_url = config.base_url.rstrip("/")

    def _get_headers(self) -> dict[str, str]:
        """Get request headers."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": f"youtube-subtitle-api-sdk/{__version__}",
        }
        if self.config.api_key:
            headers["X-API-Key"] = self.config.api_key
        return headers

    def _handle_response(self, response: httpx.Response) -> Any:
        """
        Handle HTTP response, raising exceptions for errors.

        Args:
            response: HTTP response object

        Returns:
            Response JSON data

        Raises:
            YouTubeSubtitleAPIError: For API errors
        """
        try:
            data = response.json()
        except Exception:
            data = {}

        if response.status_code >= 400:
            raise _parse_error_response(response.status_code, data)

        return data


class YouTubeSubtitleAPI(_BaseClient):
    """
    Synchronous client for the YouTube Subtitle API.

    Example:
        >>> client = YouTubeSubtitleAPI(api_key="your-api-key")
        >>> # Extract subtitles (returns cached result or queues job)
        >>> result = client.extract_subtitles("dQw4w9WgXcQ", language="en")
        >>> if "job_id" in result:
        ...     # Job was queued, wait for completion
        ...     result = client.wait_for_job(result["job_id"], timeout=60)
        >>> print(result["plain_text"])
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.expertbeacon.com",
        timeout: float = 30.0,
        max_retries: int = 3,
        webhook_secret: Optional[str] = None,
        config: Optional[Config] = None,
    ):
        """
        Initialize the client.

        Args:
            api_key: Optional API key for authenticated requests
            base_url: Base URL of the API
            timeout: Request timeout in seconds
            max_retries: Maximum retries for failed requests
            webhook_secret: Secret for webhook signature verification
            config: Pre-configured Config object (overrides other args)
        """
        if config:
            self.config = config
        else:
            self.config = Config(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout,
                max_retries=max_retries,
                webhook_secret=webhook_secret,
            )

        super().__init__(self.config)

        self._client = httpx.Client(
            timeout=self.config.timeout,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "YouTubeSubtitleAPI":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Make an HTTP request.

        Args:
            method: HTTP method
            path: Request path (will be appended to base_url)
            json_data: Optional JSON body

        Returns:
            Response JSON data
        """
        url = f"{self._base_url}{path}"
        response = self._client.request(
            method=method,
            url=url,
            headers=self._get_headers(),
            json=json_data,
        )
        return self._handle_response(response)

    def extract_subtitles(
        self,
        video_id: Optional[str] = None,
        *,
        language: str = "en",
        video_url: Optional[str] = None,
        clean_for_ai: bool = True,
        webhook_url: Optional[str] = None,
    ) -> Union[Subtitle, QueuedResponse]:
        """
        Extract subtitles for a YouTube video.

        Returns cached subtitles immediately if available,
        otherwise queues an extraction job.

        Args:
            video_id: YouTube video ID (11 characters)
            language: Subtitle language code (default: "en")
            video_url: Full YouTube URL (alternative to video_id)
            clean_for_ai: Normalize text for AI consumption
            webhook_url: Optional webhook URL for completion notification

        Returns:
            Subtitle object if cached, QueuedResponse if queued

        Raises:
            InvalidVideoIDError: If video ID or URL is invalid
            AuthenticationError: If API key is invalid
            RateLimitError: If rate limit is exceeded
            APIError: For other API errors

        Example:
            >>> # Get cached result or queue job
            >>> result = client.extract_subtitles("dQw4w9WgXcQ")
            >>> if isinstance(result, Subtitle):
            ...     print(result.plain_text)
            >>> else:
            ...     print(f"Job queued: {result.job_id}")
        """
        request = ExtractionRequest(
            video_id=video_id,
            video_url=video_url,
            language=language,
            clean_for_ai=clean_for_ai,
            webhook_url=webhook_url,
        )

        response = self._request(
            "POST",
            "/api/v1/subtitles",
            json_data=request.to_dict(),
        )

        # Check if response is a queued job (202 status)
        if "job_id" in response:
            return QueuedResponse.from_dict(response)

        # Return subtitle if cached
        return Subtitle.from_dict(response)

    def get_subtitles(
        self,
        video_id: str,
        *,
        language: str = "en",
    ) -> Subtitle:
        """
        Get cached subtitles for a video.

        This endpoint only returns cached results. Use extract_subtitles()
        to trigger extraction if not cached.

        Args:
            video_id: YouTube video ID
            language: Subtitle language code

        Returns:
            Subtitle object

        Raises:
            NotFoundError: If subtitles are not cached
            InvalidVideoIDError: If video ID is invalid
            AuthenticationError: If API key is invalid

        Example:
            >>> try:
            ...     subtitle = client.get_subtitles("dQw4w9WgXcQ")
            ...     print(subtitle.plain_text)
            ... except NotFoundError:
            ...     print("Not cached - use extract_subtitles()")
        """
        video_id = extract_video_id(video_id)

        response = self._request(
            "GET",
            f"/api/v1/subtitles/{video_id}",
        )

        return Subtitle.from_dict(response)

    def extract_batch(
        self,
        video_ids: list[str],
        *,
        language: str = "en",
        clean_for_ai: bool = True,
        webhook_url: Optional[str] = None,
    ) -> BatchExtractionResult:
        """
        Extract subtitles for multiple videos in batch.

        Videos with cached results are returned immediately.
        Others are queued for extraction.

        Args:
            video_ids: List of YouTube video IDs (max 100)
            language: Subtitle language code
            clean_for_ai: Normalize text for AI consumption
            webhook_url: Optional webhook URL for completion notifications

        Returns:
            BatchExtractionResult with job IDs and cached video IDs

        Raises:
            ValidationError: If video_ids is invalid
            AuthenticationError: If API key is invalid
            RateLimitError: If rate limit is exceeded

        Example:
            >>> result = client.extract_batch(["id1", "id2", "id3"])
            >>> print(f"Queued: {result.queued_count}, Cached: {result.cached_count}")
            >>> for job_id in result.job_ids:
            ...     subtitle = client.wait_for_job(job_id)
        """
        request = BatchExtractionRequest(
            video_ids=video_ids,
            language=language,
            clean_for_ai=clean_for_ai,
            webhook_url=webhook_url,
        )

        response = self._request(
            "POST",
            "/api/v1/subtitles/batch",
            json_data=request.to_dict(),
        )

        return BatchExtractionResult.from_dict(response)

    def get_job_status(self, job_id: str) -> JobInfo:
        """
        Get the status of an extraction job.

        Args:
            job_id: Job identifier from extract_subtitles() or extract_batch()

        Returns:
            JobInfo object with status and result (if complete)

        Example:
            >>> job = client.get_job_status(job_id)
            >>> if job.is_complete:
            ...     print(job.subtitle.plain_text)
            >>> elif job.is_failed:
            ...     print(f"Failed: {job.exc_info}")
        """
        response = self._request(
            "GET",
            f"/api/v1/job/{job_id}",
        )

        return JobInfo.from_dict(response)

    def wait_for_job(
        self,
        job_id: str,
        *,
        timeout: float = 60.0,
        poll_interval: float = 2.0,
    ) -> Subtitle:
        """
        Wait for a job to complete and return the subtitle.

        Polls the job status until completion or timeout.

        Args:
            job_id: Job identifier
            timeout: Maximum time to wait in seconds
            poll_interval: Time between polls in seconds

        Returns:
            Subtitle object when job completes

        Raises:
            TimeoutError: If job doesn't complete within timeout
            APIError: If job fails

        Example:
            >>> subtitle = client.wait_for_job(job_id, timeout=120)
            >>> print(subtitle.plain_text)
        """
        import time

        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TimeoutError(
                    f"Job {job_id} did not complete within {timeout} seconds"
                )

            job = self.get_job_status(job_id)

            if job.is_complete:
                if job.subtitle:
                    return job.subtitle
                raise APIError(f"Job {job_id} completed but returned no result")

            if job.is_failed:
                raise APIError(
                    f"Job {job_id} failed: {job.exc_info or 'Unknown error'}"
                )

            # Wait before next poll
            time.sleep(poll_interval)

    def health(self) -> dict[str, Any]:
        """
        Check API health status.

        Returns:
            Health check response with component status

        Example:
            >>> health = client.health()
            >>> print(f"Status: {health['status']}")
        """
        return self._request("GET", "/health")


class AsyncYouTubeSubtitleAPI(_BaseClient):
    """
    Asynchronous client for the YouTube Subtitle API.

    Example:
        >>> async def main():
        ...     client = AsyncYouTubeSubtitleAPI(api_key="your-api-key")
        ...     async with client:
        ...         result = await client.extract_subtitles("dQw4w9WgXcQ")
        ...         if isinstance(result, QueuedResponse):
        ...             subtitle = await client.wait_for_job(result.job_id)
        ...         print(result.plain_text)
        >>> asyncio.run(main())
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.expertbeacon.com",
        timeout: float = 30.0,
        max_retries: int = 3,
        webhook_secret: Optional[str] = None,
        config: Optional[Config] = None,
    ):
        """
        Initialize the async client.

        Args:
            api_key: Optional API key for authenticated requests
            base_url: Base URL of the API
            timeout: Request timeout in seconds
            max_retries: Maximum retries for failed requests
            webhook_secret: Secret for webhook signature verification
            config: Pre-configured Config object (overrides other args)
        """
        if config:
            self.config = config
        else:
            self.config = Config(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout,
                max_retries=max_retries,
                webhook_secret=webhook_secret,
            )

        super().__init__(self.config)

        self._client = httpx.AsyncClient(
            timeout=self.config.timeout,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "AsyncYouTubeSubtitleAPI":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Make an async HTTP request.

        Args:
            method: HTTP method
            path: Request path (will be appended to base_url)
            json_data: Optional JSON body

        Returns:
            Response JSON data
        """
        url = f"{self._base_url}{path}"
        response = await self._client.request(
            method=method,
            url=url,
            headers=self._get_headers(),
            json=json_data,
        )
        return self._handle_response(response)

    async def extract_subtitles(
        self,
        video_id: Optional[str] = None,
        *,
        language: str = "en",
        video_url: Optional[str] = None,
        clean_for_ai: bool = True,
        webhook_url: Optional[str] = None,
    ) -> Union[Subtitle, QueuedResponse]:
        """
        Extract subtitles for a YouTube video (async).

        Returns cached subtitles immediately if available,
        otherwise queues an extraction job.

        Args:
            video_id: YouTube video ID (11 characters)
            language: Subtitle language code (default: "en")
            video_url: Full YouTube URL (alternative to video_id)
            clean_for_ai: Normalize text for AI consumption
            webhook_url: Optional webhook URL for completion notification

        Returns:
            Subtitle object if cached, QueuedResponse if queued
        """
        request = ExtractionRequest(
            video_id=video_id,
            video_url=video_url,
            language=language,
            clean_for_ai=clean_for_ai,
            webhook_url=webhook_url,
        )

        response = await self._request(
            "POST",
            "/api/v1/subtitles",
            json_data=request.to_dict(),
        )

        if "job_id" in response:
            return QueuedResponse.from_dict(response)

        return Subtitle.from_dict(response)

    async def get_subtitles(
        self,
        video_id: str,
        *,
        language: str = "en",
    ) -> Subtitle:
        """
        Get cached subtitles for a video (async).

        Args:
            video_id: YouTube video ID
            language: Subtitle language code

        Returns:
            Subtitle object
        """
        video_id = extract_video_id(video_id)

        response = await self._request(
            "GET",
            f"/api/v1/subtitles/{video_id}",
        )

        return Subtitle.from_dict(response)

    async def extract_batch(
        self,
        video_ids: list[str],
        *,
        language: str = "en",
        clean_for_ai: bool = True,
        webhook_url: Optional[str] = None,
    ) -> BatchExtractionResult:
        """
        Extract subtitles for multiple videos in batch (async).

        Args:
            video_ids: List of YouTube video IDs (max 100)
            language: Subtitle language code
            clean_for_ai: Normalize text for AI consumption
            webhook_url: Optional webhook URL for completion notifications

        Returns:
            BatchExtractionResult with job IDs and cached video IDs
        """
        request = BatchExtractionRequest(
            video_ids=video_ids,
            language=language,
            clean_for_ai=clean_for_ai,
            webhook_url=webhook_url,
        )

        response = await self._request(
            "POST",
            "/api/v1/subtitles/batch",
            json_data=request.to_dict(),
        )

        return BatchExtractionResult.from_dict(response)

    async def get_job_status(self, job_id: str) -> JobInfo:
        """
        Get the status of an extraction job (async).

        Args:
            job_id: Job identifier

        Returns:
            JobInfo object with status and result
        """
        response = await self._request(
            "GET",
            f"/api/v1/job/{job_id}",
        )

        return JobInfo.from_dict(response)

    async def wait_for_job(
        self,
        job_id: str,
        *,
        timeout: float = 60.0,
        poll_interval: float = 2.0,
    ) -> Subtitle:
        """
        Wait for a job to complete and return the subtitle (async).

        Args:
            job_id: Job identifier
            timeout: Maximum time to wait in seconds
            poll_interval: Time between polls in seconds

        Returns:
            Subtitle object when job completes
        """
        import asyncio

        start_time = asyncio.get_event_loop().time()

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                raise TimeoutError(
                    f"Job {job_id} did not complete within {timeout} seconds"
                )

            job = await self.get_job_status(job_id)

            if job.is_complete:
                if job.subtitle:
                    return job.subtitle
                raise APIError(f"Job {job_id} completed but returned no result")

            if job.is_failed:
                raise APIError(
                    f"Job {job_id} failed: {job.exc_info or 'Unknown error'}"
                )

            await asyncio.sleep(poll_interval)

    async def health(self) -> dict[str, Any]:
        """
        Check API health status (async).

        Returns:
            Health check response with component status
        """
        return await self._request("GET", "/health")

    async def extract_subtitles_batch_parallel(
        self,
        video_ids: list[str],
        *,
        language: str = "en",
        clean_for_ai: bool = True,
        concurrency: int = 5,
    ) -> list[tuple[str, Union[Subtitle, QueuedResponse, Exception]]]:
        """
        Extract subtitles for multiple videos in parallel.

        This method makes concurrent requests for better performance.

        Args:
            video_ids: List of YouTube video IDs
            language: Subtitle language code
            clean_for_ai: Normalize text for AI consumption
            concurrency: Maximum concurrent requests

        Returns:
            List of (video_id, result) tuples
        """
        import asyncio

        async def extract_one(vid: str) -> tuple[str, Union[Subtitle, QueuedResponse, Exception]]:
            try:
                result = await self.extract_subtitles(
                    video_id=vid,
                    language=language,
                    clean_for_ai=clean_for_ai,
                )
                return (vid, result)
            except Exception as e:
                return (vid, e)

        semaphore = asyncio.Semaphore(concurrency)

        async def bounded_extract(vid: str) -> tuple[str, Union[Subtitle, QueuedResponse, Exception]]:
            async with semaphore:
                return await extract_one(vid)

        tasks = [bounded_extract(vid) for vid in video_ids]
        return await asyncio.gather(*tasks)
