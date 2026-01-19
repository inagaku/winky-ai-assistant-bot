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


def parse_relative_time_adjustment(text: str) -> Optional[int]:
    """
    Parse relative time adjustment like "1 hour earlier" or "30 minutes later".

    Returns:
        Minutes to adjust (negative for earlier, positive for later).
        None if parsing fails.
    """
    if not text:
        return None

    text = text.lower().strip()

    # Determine direction
    is_earlier = any(word in text for word in ['earlier', 'before', 'раньше', 'назад'])
    is_later = any(word in text for word in ['later', 'after', 'позже', 'позднее', 'вперед', 'вперёд'])

    if not is_earlier and not is_later:
        return None

    # Parse the duration part
    duration = parse_duration(text)
    if duration is None:
        return None

    return -duration if is_earlier else duration


def parse_time_adjustment(text: str, current_time: datetime) -> Optional[datetime]:
    """
    Parse time adjustment and return new datetime.

    Supports:
    - Relative: "1 hour earlier", "30 minutes later", "2 hours before"
    - Absolute time (keeps date): "3pm", "15:30", "at 4 o'clock"

    Args:
        text: User input for time adjustment
        current_time: Current reminder time to adjust

    Returns:
        New datetime, or None if parsing fails
    """
    if not text:
        return None

    text_lower = text.lower().strip()

    # Try relative adjustment first
    relative_minutes = parse_relative_time_adjustment(text_lower)
    if relative_minutes is not None:
        return current_time + timedelta(minutes=relative_minutes)

    # Try absolute time (HH:MM or "3pm" style) - keep the date
    time_patterns = [
        # 24-hour format: 14:30, 9:00
        (r'^(\d{1,2}):(\d{2})$', lambda m: (int(m.group(1)), int(m.group(2)))),
        # 12-hour format with am/pm: 3pm, 3:30pm, 3 pm
        (r'^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$', lambda m: (
            int(m.group(1)) % 12 + (12 if m.group(3) == 'pm' else 0),
            int(m.group(2)) if m.group(2) else 0
        )),
        # "at X" format: at 3pm, at 15:30
        (r'^at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$', lambda m: (
            (int(m.group(1)) % 12 + (12 if m.group(3) == 'pm' else 0)) if m.group(3) else int(m.group(1)),
            int(m.group(2)) if m.group(2) else 0
        )),
    ]

    for pattern, extractor in time_patterns:
        match = re.match(pattern, text_lower)
        if match:
            try:
                hour, minute = extractor(match)
                if 0 <= hour < 24 and 0 <= minute < 60:
                    return current_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
            except (ValueError, TypeError):
                continue

    return None


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
