"""
Exception classes for the YouTube Subtitle API SDK.

This module defines all exceptions raised by the SDK, organized
by error type for easy catching and handling.
"""

from __future__ import annotations

from typing import Any, Optional


class YouTubeSubtitleAPIError(Exception):
    """
    Base exception for all YouTube Subtitle API errors.

    All exceptions raised by the SDK inherit from this class,
    allowing you to catch all SDK errors with a single except clause.

    Example:
        >>> try:
        ...     client.extract_subtitles("video_id")
        ... except YouTubeSubtitleAPIError as e:
        ...     print(f"API Error: {e}")
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        hint: Optional[str] = None,
        error_code: Optional[str] = None,
    ):
        """
        Initialize the exception.

        Args:
            message: Error message
            status_code: HTTP status code (if applicable)
            hint: Helpful hint for resolving the error
            error_code: API error code (if applicable)
        """
        self.message = message
        self.status_code = status_code
        self.hint = hint
        self.error_code = error_code
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format the full error message with hint."""
        parts = [self.message]
        if self.hint:
            parts.append(f"Hint: {self.hint}")
        if self.status_code:
            parts.append(f"Status Code: {self.status_code}")
        return " | ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert exception to dictionary.

        Returns:
            Dictionary representation of the error
        """
        data = {
            "error": self.__class__.__name__,
            "message": self.message,
        }
        if self.status_code:
            data["status_code"] = self.status_code
        if self.hint:
            data["hint"] = self.hint
        if self.error_code:
            data["error_code"] = self.error_code
        return data


class APIError(YouTubeSubtitleAPIError):
    """
    Generic API error for unexpected responses.

    Raised when the API returns an error that doesn't match
    a specific error type.

    Example:
        >>> try:
        ...     client.extract_subtitles("video_id")
        ... except APIError as e:
        ...     print(f"API returned error: {e.message}")
    """

    pass


class AuthenticationError(YouTubeSubtitleAPIError):
    """
    Raised when authentication fails.

    This occurs when:
    - API key is missing or invalid
    - Token has expired
    - Credentials are not authorized for the requested resource

    Example:
        >>> try:
        ...     client.extract_subtitles("video_id")
        ... except AuthenticationError:
        ...     print("Check your API key")
    """

    def __init__(
        self,
        message: str = "Authentication required",
        *,
        hint: Optional[str] = "Provide a valid API key via X-API-Key header",
    ):
        super().__init__(
            message=message,
            status_code=401,
            hint=hint,
            error_code="UNAUTHORIZED",
        )


class RateLimitError(YouTubeSubtitleAPIError):
    """
    Raised when the API rate limit is exceeded.

    This occurs when too many requests are made within a time window.
    Implement exponential backoff and retry after the indicated time.

    Example:
        >>> import time
        >>> try:
        ...     client.extract_subtitles("video_id")
        ... except RateLimitError as e:
        ...     print(f"Rate limited. Wait before retrying.")
        ...     time.sleep(60)  # Wait before retry
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        *,
        hint: Optional[str] = "Wait before making another request or upgrade your API plan",
        retry_after: Optional[int] = None,
    ):
        super().__init__(
            message=message,
            status_code=429,
            hint=hint,
            error_code="RATE_LIMIT_EXCEEDED",
        )
        self.retry_after = retry_after


class NotFoundError(YouTubeSubtitleAPIError):
    """
    Raised when a requested resource is not found.

    This occurs when:
    - Requested video ID doesn't exist
    - Subtitles are not available for the video
    - Cached subtitles have expired

    Example:
        >>> try:
        ...     client.get_subtitles("video_id")
        ... except NotFoundError:
        ...     print("Subtitles not found, use extract_subtitles() to trigger extraction")
    """

    def __init__(
        self,
        message: str = "Resource not found",
        *,
        hint: Optional[str] = None,
        resource_type: str = "subtitle",
    ):
        if hint is None:
            hint = f"The {resource_type} may not exist or may not be available"
        super().__init__(
            message=message,
            status_code=404,
            hint=hint,
            error_code="SUBTITLE_NOT_FOUND",
        )
        self.resource_type = resource_type


class ValidationError(YouTubeSubtitleAPIError):
    """
    Raised when request validation fails.

    This occurs when:
    - Invalid video ID format
    - Missing required parameters
    - Invalid parameter values

    Example:
        >>> try:
        ...     client.extract_subtitles("invalid_id")
        ... except ValidationError as e:
        ...     print(f"Validation error: {e.message}")
    """

    def __init__(
        self,
        message: str = "Invalid request",
        *,
        hint: Optional[str] = "Check your request parameters and try again",
        field: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            status_code=400,
            hint=hint,
            error_code="INVALID_REQUEST",
        )
        self.field = field


class InvalidVideoIDError(ValidationError):
    """
    Raised specifically for invalid YouTube video IDs.

    Example:
        >>> try:
        ...     client.extract_subtitles("not_a_valid_id")
        ... except InvalidVideoIDError as e:
        ...     print(f"Invalid video ID: {e.message}")
    """

    def __init__(
        self,
        message: str = "Invalid YouTube video ID",
        *,
        video_id: Optional[str] = None,
    ):
        hint = "Provide a valid 11-character video ID or full YouTube URL"
        if video_id:
            message = f"Invalid YouTube video ID: {video_id}"
        super().__init__(message=message, hint=hint, field="video_id")
        self.video_id = video_id


class ServiceUnavailableError(YouTubeSubtitleAPIError):
    """
    Raised when the API service is temporarily unavailable.

    This occurs when:
    - API is under maintenance
    - Service is overloaded
    - Internal server error

    Example:
        >>> import time
        >>> try:
        ...     client.extract_subtitles("video_id")
        ... except ServiceUnavailableError:
        ...     time.sleep(30)  # Wait and retry
    """

    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        *,
        hint: Optional[str] = "The service is experiencing issues. Please try again later",
    ):
        super().__init__(
            message=message,
            status_code=503,
            hint=hint,
            error_code="SERVICE_UNAVAILABLE",
        )


class TimeoutError(YouTubeSubtitleAPIError):
    """
    Raised when a request times out.

    This occurs when:
    - Network timeout
    - Job doesn't complete within expected time
    - Server takes too long to respond

    Example:
        >>> try:
        ...     client.wait_for_job(job_id, timeout=30)
        ... except TimeoutError:
        ...     print("Job took too long, try increasing timeout")
    """

    def __init__(
        self,
        message: str = "Request timed out",
        *,
        hint: Optional[str] = "Try again later or increase the timeout value",
    ):
        super().__init__(message=message, hint=hint)


class NetworkError(YouTubeSubtitleAPIError):
    """
    Raised when a network error occurs.

    This occurs when:
    - Connection refused
    - DNS resolution fails
    - Network unreachable

    Example:
        >>> try:
        ...     client.extract_subtitles("video_id")
        ... except NetworkError:
        ...     print("Network error, check your connection")
    """

    def __init__(
        self,
        message: str = "Network error",
        *,
        hint: Optional[str] = "Check your network connection and try again",
    ):
        super().__init__(message=message, hint=hint)
