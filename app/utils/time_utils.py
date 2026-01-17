"""Time utilities for timezone-aware datetime handling."""

import re
from datetime import datetime, timezone, timedelta
from typing import Optional


def utc_now() -> datetime:
    """
    Get current UTC time as timezone-aware datetime.

    This replaces the deprecated datetime.utcnow() which returns
    a naive datetime. Returns timezone-aware datetime in UTC.
    """
    return datetime.now(timezone.utc)


def parse_duration(duration_str: str) -> Optional[int]:
    """
    Parse a duration string into minutes.

    Supports formats like:
    - "30 minutes", "30 min", "30m"
    - "1 hour", "2 hours", "1.5 hours", "1h"
    - "1 hour 30 minutes", "1h 30m"
    - "90 minutes before", "1 hour before"

    Args:
        duration_str: Natural language duration string

    Returns:
        Duration in minutes, or None if parsing fails
    """
    if not duration_str:
        return None

    text = duration_str.lower().strip()

    # Remove "before" or "earlier" suffixes
    text = re.sub(r'\s*(before|earlier|in advance|prior)$', '', text)

    total_minutes = 0

    # Pattern for hours (including decimals)
    hour_patterns = [
        r'(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b',
    ]
    for pattern in hour_patterns:
        match = re.search(pattern, text)
        if match:
            hours = float(match.group(1))
            total_minutes += int(hours * 60)
            text = re.sub(pattern, '', text)

    # Pattern for minutes
    minute_patterns = [
        r'(\d+)\s*(?:minutes?|mins?|m)\b',
    ]
    for pattern in minute_patterns:
        match = re.search(pattern, text)
        if match:
            minutes = int(match.group(1))
            total_minutes += minutes
            text = re.sub(pattern, '', text)

    # If we found any time units, return the total
    if total_minutes > 0:
        return total_minutes

    # Try to parse standalone number as minutes
    standalone_match = re.match(r'^(\d+)$', text.strip())
    if standalone_match:
        return int(standalone_match.group(1))

    return None
