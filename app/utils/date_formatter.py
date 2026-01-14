"""Date formatting utilities with locale and timezone support."""

from datetime import datetime
from typing import Optional
import pytz

# Month names by locale
MONTH_NAMES = {
    "en": [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
    ],
    "ru": [
        "янв", "фев", "мар", "апр", "мая", "июн",
        "июл", "авг", "сен", "окт", "ноя", "дек"
    ],
}

MONTH_NAMES_FULL = {
    "en": [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ],
    "ru": [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря"
    ],
}


def utc_to_local(dt: datetime, timezone: str) -> datetime:
    """Convert UTC datetime to local timezone."""
    if dt is None:
        return None

    # Ensure datetime is timezone aware (assume UTC if naive)
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)

    try:
        local_tz = pytz.timezone(timezone)
        return dt.astimezone(local_tz)
    except Exception:
        # Return as-is if timezone conversion fails
        return dt


def format_datetime(
    dt: datetime,
    locale: str = "en",
    timezone: Optional[str] = None,
    include_time: bool = True,
    short_month: bool = True,
) -> str:
    """
    Format datetime in a human-readable, locale-aware format.

    Args:
        dt: The datetime to format
        locale: Language code (en, ru)
        timezone: User's timezone (converts from UTC if provided)
        include_time: Whether to include time (HH:MM)
        short_month: Use short month names (Jan vs January)

    Returns:
        Formatted string like "14 Jan 2026 15:30" or "14 янв 2026 15:30"
    """
    if dt is None:
        return ""

    # Convert to local timezone if provided
    if timezone:
        dt = utc_to_local(dt, timezone)

    # Get month name
    month_names = MONTH_NAMES if short_month else MONTH_NAMES_FULL
    month_list = month_names.get(locale, month_names["en"])
    month_name = month_list[dt.month - 1]

    # Format date
    if include_time:
        return f"{dt.day} {month_name} {dt.year} {dt.hour:02d}:{dt.minute:02d}"
    else:
        return f"{dt.day} {month_name} {dt.year}"


def format_date(
    dt: datetime,
    locale: str = "en",
    timezone: Optional[str] = None,
) -> str:
    """Format date only (no time)."""
    return format_datetime(dt, locale, timezone, include_time=False)


def format_time(
    dt: datetime,
    timezone: Optional[str] = None,
) -> str:
    """Format time only (HH:MM)."""
    if dt is None:
        return ""

    if timezone:
        dt = utc_to_local(dt, timezone)

    return f"{dt.hour:02d}:{dt.minute:02d}"


def format_short_datetime(
    dt: datetime,
    locale: str = "en",
    timezone: Optional[str] = None,
) -> str:
    """
    Format datetime in short format for lists (MM/DD HH:MM or DD.MM HH:MM).

    Args:
        dt: The datetime to format
        locale: Language code
        timezone: User's timezone

    Returns:
        Formatted string like "01/14 15:30" (en) or "14.01 15:30" (ru)
    """
    if dt is None:
        return ""

    if timezone:
        dt = utc_to_local(dt, timezone)

    if locale == "ru":
        return f"{dt.day:02d}.{dt.month:02d} {dt.hour:02d}:{dt.minute:02d}"
    else:
        return f"{dt.month:02d}/{dt.day:02d} {dt.hour:02d}:{dt.minute:02d}"
