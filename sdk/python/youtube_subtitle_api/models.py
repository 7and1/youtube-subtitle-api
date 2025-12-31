"""
Data models for the YouTube Subtitle API SDK.

This module defines the data structures used throughout the SDK,
including subtitle items, job status enums, and webhook events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class JobStatus(str, Enum):
    """
    Status of an extraction job.

    Attributes:
        QUEUED: Job is in the queue waiting to be processed
        STARTED: Job has started processing
        FINISHED: Job completed successfully
        FAILED: Job failed with an error
        UNKNOWN: Status is unknown or not recognized
    """

    QUEUED = "queued"
    STARTED = "started"
    FINISHED = "finished"
    FAILED = "failed"
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, value: str) -> "JobStatus":
        """
        Create JobStatus from string value.

        Args:
            value: String representation of the status

        Returns:
            JobStatus enum value
        """
        try:
            return cls(value.lower())
        except ValueError:
            return cls.UNKNOWN


@dataclass(frozen=True)
class SubtitleItem:
    """
    A single subtitle entry with timing information.

    Attributes:
        text: The subtitle text content
        start: Start time in seconds
        end: End time in seconds
        dur: Duration in seconds
    """

    text: str
    start: float
    end: float
    dur: Optional[float] = None

    def __post_init__(self):
        """Calculate duration if not provided."""
        if self.dur is None:
            object.__setattr__(self, "dur", self.end - self.start)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubtitleItem":
        """
        Create SubtitleItem from API response dictionary.

        Args:
            data: Dictionary with subtitle item data

        Returns:
            SubtitleItem instance
        """
        # Handle different possible field names
        text = data.get("text", "")
        start = float(data.get("start", 0))
        end = float(data.get("end", 0))
        dur = data.get("dur")

        return cls(text=text, start=start, end=end, dur=dur)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "dur": self.dur,
        }

    @property
    def start_timestamp(self) -> str:
        """
        Get start time in SRT timestamp format (HH:MM:SS,mmm).

        Returns:
            Formatted timestamp string
        """
        hours = int(self.start // 3600)
        minutes = int((self.start % 3600) // 60)
        seconds = int(self.start % 60)
        milliseconds = int((self.start % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    @property
    def end_timestamp(self) -> str:
        """
        Get end time in SRT timestamp format (HH:MM:SS,mmm).

        Returns:
            Formatted timestamp string
        """
        hours = int(self.end // 3600)
        minutes = int((self.end % 3600) // 60)
        seconds = int(self.end % 60)
        milliseconds = int((self.end % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    def to_srt(self, index: int) -> str:
        """
        Format subtitle item as SRT entry.

        Args:
            index: Subtitle index number

        Returns:
            SRT formatted string
        """
        return f"{index}\n{self.start_timestamp} --> {self.end_timestamp}\n{self.text}\n"


@dataclass
class Subtitle:
    """
    Complete subtitle data for a YouTube video.

    Attributes:
        video_id: YouTube video ID
        title: Video title (if available)
        language: Subtitle language code
        extraction_method: Method used to extract subtitles
        subtitle_count: Number of subtitle items
        duration_ms: Extraction duration in milliseconds
        subtitles: List of individual subtitle items
        plain_text: Full transcript as plain text
        cached: Whether result came from cache
        cache_tier: Cache tier that returned the result
        created_at: When the subtitle was created
        proxy_used: Proxy used for extraction (if any)
    """

    video_id: str
    language: str
    subtitles: list[SubtitleItem]
    plain_text: Optional[str] = None
    title: Optional[str] = None
    extraction_method: Optional[str] = None
    subtitle_count: int = 0
    duration_ms: int = 0
    cached: bool = False
    cache_tier: Optional[str] = None
    created_at: Optional[str] = None
    proxy_used: Optional[str] = None

    def __post_init__(self):
        """Calculate derived fields."""
        if self.subtitle_count == 0 and self.subtitles:
            object.__setattr__(self, "subtitle_count", len(self.subtitles))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Subtitle":
        """
        Create Subtitle from API response dictionary.

        Args:
            data: Dictionary with subtitle data

        Returns:
            Subtitle instance
        """
        subtitles_data = data.get("subtitles", [])
        subtitles = [
            SubtitleItem.from_dict(item) if isinstance(item, dict) else item
            for item in subtitles_data
        ]

        return cls(
            video_id=data.get("video_id", ""),
            language=data.get("language", "en"),
            subtitles=subtitles,
            plain_text=data.get("plain_text"),
            title=data.get("title"),
            extraction_method=data.get("extraction_method"),
            subtitle_count=data.get("subtitle_count", len(subtitles)),
            duration_ms=data.get("duration_ms", 0),
            cached=data.get("cached", False),
            cache_tier=data.get("cache_tier"),
            created_at=data.get("created_at"),
            proxy_used=data.get("proxy_used"),
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "video_id": self.video_id,
            "title": self.title,
            "language": self.language,
            "extraction_method": self.extraction_method,
            "subtitle_count": self.subtitle_count,
            "duration_ms": self.duration_ms,
            "subtitles": [s.to_dict() for s in self.subtitles],
            "plain_text": self.plain_text,
            "cached": self.cached,
            "cache_tier": self.cache_tier,
            "created_at": self.created_at,
            "proxy_used": self.proxy_used,
        }

    def to_srt(self) -> str:
        """
        Export subtitles in SRT format.

        Returns:
            SRT formatted string
        """
        lines = []
        for i, item in enumerate(self.subtitles, start=1):
            lines.append(item.to_srt(i))
        return "\n".join(lines)

    def to_vtt(self) -> str:
        """
        Export subtitles in WebVTT format.

        Returns:
            WebVTT formatted string
        """
        lines = ["WEBVTT\n"]
        for item in self.subtitles:
            lines.append(f"\n{item.start_timestamp} --> {item.end_timestamp}\n{item.text}\n")
        return "".join(lines)

    def get_text_by_time_range(
        self, start: float, end: Optional[float] = None
    ) -> list[SubtitleItem]:
        """
        Get subtitle items within a time range.

        Args:
            start: Start time in seconds
            end: Optional end time in seconds (defaults to end of video)

        Returns:
            List of subtitle items in the time range
        """
        items = []
        for item in self.subtitles:
            if item.start >= start:
                if end is None or item.start <= end:
                    items.append(item)
                else:
                    break
        return items

    def search_text(self, query: str, case_sensitive: bool = False) -> list[SubtitleItem]:
        """
        Search for subtitle items containing the query text.

        Args:
            query: Text to search for
            case_sensitive: Whether to use case-sensitive search

        Returns:
            List of matching subtitle items
        """
        if not case_sensitive:
            query = query.lower()

        items = []
        for item in self.subtitles:
            text = item.text if case_sensitive else item.text.lower()
            if query in text:
                items.append(item)
        return items

    @property
    def total_duration(self) -> float:
        """
        Get total duration of subtitles in seconds.

        Returns:
            Duration in seconds
        """
        if not self.subtitles:
            return 0.0
        return self.subtitles[-1].end

    @property
    def word_count(self) -> int:
        """
        Get total word count of the transcript.

        Returns:
            Number of words
        """
        if self.plain_text:
            return len(self.plain_text.split())
        return sum(len(item.text.split()) for item in self.subtitles)


@dataclass(frozen=True)
class WebhookEvent:
    """
    Webhook event received from the API.

    Attributes:
        event: Event type (e.g., "job.completed")
        job_id: Job identifier
        video_id: YouTube video ID
        status: Job status ("success" or "failed")
        result: Result data for successful jobs
        error: Error message for failed jobs
        timestamp: ISO timestamp of the event
    """

    event: str
    job_id: str
    video_id: str
    status: str
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WebhookEvent":
        """
        Create WebhookEvent from webhook payload.

        Args:
            data: Webhook payload dictionary

        Returns:
            WebhookEvent instance
        """
        return cls(
            event=data.get("event", ""),
            job_id=data.get("job_id", ""),
            video_id=data.get("video_id", ""),
            status=data.get("status", ""),
            result=data.get("result"),
            error=data.get("error"),
            timestamp=data.get("timestamp"),
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "event": self.event,
            "job_id": self.job_id,
            "video_id": self.video_id,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "timestamp": self.timestamp,
        }

    @property
    def is_success(self) -> bool:
        """Check if the job completed successfully."""
        return self.status == "success"

    @property
    def is_failed(self) -> bool:
        """Check if the job failed."""
        return self.status == "failed"

    @property
    def subtitle(self) -> Optional[Subtitle]:
        """Get Subtitle object if job was successful."""
        if self.is_success and self.result:
            return Subtitle.from_dict(self.result)
        return None
