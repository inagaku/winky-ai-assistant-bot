"""Time utilities for timezone-aware datetime handling."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """
    Get current UTC time as timezone-aware datetime.

    This replaces the deprecated datetime.utcnow() which returns
    a naive datetime. Returns timezone-aware datetime in UTC.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
