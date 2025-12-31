"""init

Revision ID: 20251230_0001
Revises:
Create Date: 2025-12-30
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20251230_0001"
down_revision = None
branch_labels = None
depends_on = None


def _schema() -> str:
    return os.getenv("DB_SCHEMA", "youtube_subtitles")


def upgrade() -> None:
    schema = _schema()
    op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))

    op.create_table(
        "subtitle_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", sa.String(length=11), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("subtitles", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("plain_text", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=5), nullable=False),
        sa.Column("auto_generated", sa.Boolean(), nullable=True),
        sa.Column("extraction_method", sa.String(length=50), nullable=False),
        sa.Column("extraction_duration_ms", sa.Integer(), nullable=True),
        sa.Column("extraction_status", sa.String(length=20), nullable=True),
        sa.Column("extraction_error", sa.String(length=500), nullable=True),
        sa.Column("proxy_used", sa.String(length=255), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=True),
        sa.Column("last_retry_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("video_id", "language", name="uq_video_language"),
        schema=schema,
    )
    op.create_index("ix_video_id", "subtitle_records", ["video_id"], unique=False, schema=schema)
    op.create_index("ix_created_at", "subtitle_records", ["created_at"], unique=False, schema=schema)
    op.create_index("ix_status", "subtitle_records", ["extraction_status"], unique=False, schema=schema)

    op.create_table(
        "extraction_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", sa.String(length=11), nullable=False),
        sa.Column("language", sa.String(length=5), nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("job_status", sa.String(length=20), nullable=True),
        sa.Column("result_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=True),
        sa.Column("max_attempts", sa.Integer(), nullable=True),
        sa.UniqueConstraint("job_id", name="uq_job_id"),
        schema=schema,
    )
    op.create_index("ix_video_id_job", "extraction_jobs", ["video_id"], unique=False, schema=schema)
    op.create_index("ix_job_status", "extraction_jobs", ["job_status"], unique=False, schema=schema)
    op.create_index("ix_created_at_job", "extraction_jobs", ["created_at"], unique=False, schema=schema)
    # PERFORMANCE: Composite index for pending job queries
    # Query pattern: WHERE video_id = ? AND language = ? AND job_status IN (?, ?)
    # This index supports the get_pending_job() query in subtitle_repository.py
    op.create_index(
        "ix_pending_jobs_lookup",
        "extraction_jobs",
        ["video_id", "language", "job_status"],
        unique=False,
        schema=schema,
    )


def downgrade() -> None:
    schema = _schema()
    op.drop_index("ix_pending_jobs_lookup", schema=schema)
    op.drop_table("extraction_jobs", schema=schema)
    op.drop_table("subtitle_records", schema=schema)
