"""add_webhook_support

Revision ID: 20251231_0002
Revises: 20251230_0001
Create Date: 2025-12-31

This migration adds webhook support to the extraction_jobs table.
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20251231_0002"
down_revision = "20251230_0001"
branch_labels = None
depends_on = None


def _schema() -> str:
    return os.getenv("DB_SCHEMA", "youtube_subtitles")


def upgrade() -> None:
    schema = _schema()

    # Add webhook columns to extraction_jobs table
    with op.batch_alter_table("extraction_jobs", schema=schema) as batch_op:
        batch_op.add_column(
            sa.Column(
                "webhook_url",
                sa.String(length=500),
                nullable=True,
                comment="URL to send job completion webhook",
            )
        )
        batch_op.add_column(
            sa.Column(
                "webhook_delivered",
                sa.Boolean(),
                nullable=True,
                server_default="false",
                comment="Whether webhook has been delivered",
            )
        )
        batch_op.add_column(
            sa.Column(
                "webhook_delivery_status",
                sa.String(length=50),
                nullable=True,
                comment="Webhook delivery status: pending, delivered, failed",
            )
        )
        batch_op.add_column(
            sa.Column(
                "webhook_delivery_error",
                sa.String(length=500),
                nullable=True,
                comment="Error message if webhook delivery failed",
            )
        )

    # Create index on webhook_delivery_status for monitoring failed webhooks
    op.create_index(
        "ix_webhook_delivery_status",
        "extraction_jobs",
        ["webhook_delivery_status"],
        unique=False,
        schema=schema,
    )


def downgrade() -> None:
    schema = _schema()

    # Drop the index
    op.drop_index(
        "ix_webhook_delivery_status",
        table_name="extraction_jobs",
        schema=schema,
    )

    # Remove webhook columns from extraction_jobs table
    with op.batch_alter_table("extraction_jobs", schema=schema) as batch_op:
        batch_op.drop_column("webhook_delivery_error")
        batch_op.drop_column("webhook_delivery_status")
        batch_op.drop_column("webhook_delivered")
        batch_op.drop_column("webhook_url")
