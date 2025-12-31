"""
SQLAlchemy models for subtitle data persistence.
"""

from datetime import datetime, timezone
import os
import uuid
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    Float,
    Boolean,
    Index,
    UniqueConstraint,
    Text,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import UUID, JSONB

DB_SCHEMA = os.getenv("DB_SCHEMA", "youtube_subtitles")

Base = declarative_base()


def _utc_now() -> datetime:
    """
    Get current UTC timestamp as naive datetime.

    DEPRECATION FIX: datetime.utcnow() is deprecated in Python 3.12+.
    Use datetime.now(timezone.utc) and remove tzinfo for compatibility
    with existing timezone-naive database columns.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SubtitleRecord(Base):
    """Model for storing extracted subtitles."""

    __tablename__ = "subtitle_records"
    __table_args__ = (
        Index("ix_video_id", "video_id"),
        Index("ix_created_at", "created_at"),
        Index("ix_status", "extraction_status"),
        UniqueConstraint("video_id", "language", name="uq_video_language"),
        {"schema": DB_SCHEMA},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Video metadata
    video_id = Column(String(11), nullable=False)
    title = Column(String(255), nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Subtitle content
    subtitles = Column(JSONB, nullable=True)  # Array of {start, end, text, confidence}
    plain_text = Column(Text, nullable=True)
    language = Column(String(5), default="en")
    auto_generated = Column(Boolean, default=False)

    # Extraction metadata
    extraction_method = Column(
        String(50), nullable=False
    )  # youtube-transcript-api, yt-dlp
    extraction_duration_ms = Column(Integer, nullable=True)
    extraction_status = Column(
        String(20), default="pending"
    )  # pending, success, failed, timeout
    extraction_error = Column(String(500), nullable=True)
    proxy_used = Column(String(255), nullable=True)

    # Cache management
    checksum = Column(
        String(64), nullable=True
    )  # SHA256 of content (for change detection)
    created_at = Column(DateTime, default=_utc_now, nullable=False)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)
    expires_at = Column(DateTime, nullable=True)  # For TTL-based cleanup

    # Retry tracking
    retry_count = Column(Integer, default=0)
    last_retry_at = Column(DateTime, nullable=True)

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "video_id": self.video_id,
            "title": self.title,
            "duration_seconds": self.duration_seconds,
            "subtitles": self.subtitles,
            "plain_text": self.plain_text,
            "language": self.language,
            "auto_generated": self.auto_generated,
            "extraction_method": self.extraction_method,
            "extraction_duration_ms": self.extraction_duration_ms,
            "extraction_status": self.extraction_status,
            "created_at": self.created_at.isoformat() + "Z",
            "updated_at": self.updated_at.isoformat() + "Z",
        }


class ExtractionJob(Base):
    """Model for tracking async extraction jobs."""

    __tablename__ = "extraction_jobs"
    __table_args__ = (
        Index("ix_video_id_job", "video_id"),
        Index("ix_job_status", "job_status"),
        Index("ix_created_at_job", "created_at"),
        {"schema": DB_SCHEMA},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Job reference
    video_id = Column(String(11), nullable=False)
    language = Column(String(5), default="en")
    job_id = Column(String(64), nullable=False, unique=True)  # RQ job ID

    # Job state
    job_status = Column(
        String(20), default="queued"
    )  # queued, processing, completed, failed, timeout
    result_data = Column(JSONB, nullable=True)
    error_message = Column(String(500), nullable=True)

    # Webhook configuration
    webhook_url = Column(String(500), nullable=True)
    webhook_delivered = Column(Boolean, default=False)
    webhook_delivery_status = Column(String(50), nullable=True)  # pending, delivered, failed
    webhook_delivery_error = Column(String(500), nullable=True)

    # Timing
    created_at = Column(DateTime, default=_utc_now, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # Retry info
    attempt = Column(Integer, default=1)
    max_attempts = Column(Integer, default=3)

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "job_id": self.job_id,
            "video_id": self.video_id,
            "status": self.job_status,
            "attempt": self.attempt,
            "created_at": self.created_at.isoformat() + "Z",
            "completed_at": (
                self.completed_at.isoformat() + "Z" if self.completed_at else None
            ),
        }
