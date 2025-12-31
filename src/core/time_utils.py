from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """
    UTC "now" as a naive datetime.

    We intentionally return a naive datetime to stay compatible with existing
    DB columns defined as timezone-naive timestamps.
    """

    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc_now_iso_z() -> str:
    """UTC timestamp as ISO8601 with trailing 'Z'."""

    return utc_now().isoformat() + "Z"
