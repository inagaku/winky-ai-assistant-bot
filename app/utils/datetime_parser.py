"""Intelligent datetime parser using LLM for natural language understanding."""

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# Default timezone - can be made configurable per user
DEFAULT_TIMEZONE = "UTC"


class DateTimeParser:
    """
    Intelligent datetime parser that converts natural language to datetime.

    Uses OpenAI LLM to understand expressions like:
    - "tomorrow at 3pm"
    - "next Monday morning"
    - "in 2 hours"
    - "the day after tomorrow at noon"
    - "this Friday evening"
    - "January 15th at 2:30pm"
    """

    SYSTEM_PROMPT = """You are a datetime parser. Convert natural language time expressions to structured datetime.

Current reference time: {current_time}
Current day of week: {day_of_week}
Timezone: {timezone}

Parse the user's time expression and return a JSON object with:
{{
    "year": <int>,
    "month": <int 1-12>,
    "day": <int 1-31>,
    "hour": <int 0-23>,
    "minute": <int 0-59>,
    "confidence": <float 0-1 how confident you are>,
    "interpretation": "<brief explanation of how you interpreted this>"
}}

Rules:
- "morning" = 9:00
- "noon" = 12:00
- "afternoon" = 14:00
- "evening" = 18:00
- "night" = 21:00
- "end of day" = 17:00
- If no time specified for a reminder/task, default to 9:00
- If no time specified for a meeting, default to 10:00
- "next week" without day = next Monday
- "this weekend" = Saturday
- "in X hours/minutes" = relative to current time
- Always use 24-hour format internally

Return ONLY the JSON object, no other text."""

    def __init__(self, openai_api_key: str, default_timezone: str = DEFAULT_TIMEZONE):
        self.client = AsyncOpenAI(api_key=openai_api_key)
        self.default_timezone = default_timezone

    async def parse(
        self,
        text: str,
        reference_time: Optional[datetime] = None,
        timezone: Optional[str] = None,
        context_type: str = "reminder",  # "reminder", "task", "meeting"
    ) -> Tuple[Optional[datetime], float, str]:
        """
        Parse a natural language datetime expression.

        Args:
            text: The natural language time expression
            reference_time: Reference time for relative expressions (defaults to now)
            timezone: User's timezone (defaults to UTC)
            context_type: Type of item being created (affects default times)

        Returns:
            Tuple of (parsed_datetime, confidence, interpretation)
            Returns (None, 0.0, error_message) if parsing fails
        """
        if not text:
            return None, 0.0, "No datetime text provided"

        tz = ZoneInfo(timezone or self.default_timezone)
        now = reference_time or datetime.now(tz)

        # First try quick local parsing for common patterns
        quick_result = self._quick_parse(text, now, context_type)
        if quick_result[0] is not None and quick_result[1] >= 0.9:
            return quick_result

        # Fall back to LLM for complex expressions
        try:
            system_prompt = self.SYSTEM_PROMPT.format(
                current_time=now.strftime("%Y-%m-%d %H:%M"),
                day_of_week=now.strftime("%A"),
                timezone=timezone or self.default_timezone,
            )

            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Parse this time expression for a {context_type}: \"{text}\""},
                ],
                temperature=0.1,
                max_tokens=200,
            )

            result_text = response.choices[0].message.content.strip()

            # Extract JSON from response
            json_match = re.search(r'\{[^{}]+\}', result_text, re.DOTALL)
            if not json_match:
                logger.warning(f"No JSON found in LLM response: {result_text}")
                return self._fallback_parse(text, now, context_type)

            result = json.loads(json_match.group())

            parsed_dt = datetime(
                year=result["year"],
                month=result["month"],
                day=result["day"],
                hour=result.get("hour", 9),
                minute=result.get("minute", 0),
                tzinfo=tz,
            )

            return (
                parsed_dt,
                result.get("confidence", 0.8),
                result.get("interpretation", "Parsed by LLM"),
            )

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM JSON response: {e}")
            return self._fallback_parse(text, now, context_type)
        except Exception as e:
            logger.error(f"LLM datetime parsing failed: {e}")
            return self._fallback_parse(text, now, context_type)

    def _quick_parse(
        self,
        text: str,
        now: datetime,
        context_type: str,
    ) -> Tuple[Optional[datetime], float, str]:
        """Quick local parsing for common patterns without LLM."""
        text_lower = text.lower().strip()

        # Default time based on context
        default_hour = 9 if context_type == "reminder" else 10 if context_type == "meeting" else 18

        def to_utc(dt: datetime) -> datetime:
            """Convert timezone-aware datetime to naive UTC."""
            return dt.astimezone(ZoneInfo("UTC"))

        # Pattern: "in X hours/minutes"
        in_match = re.match(r'in\s+(\d+)\s*(hour|hr|minute|min)s?', text_lower)
        if in_match:
            amount = int(in_match.group(1))
            unit = in_match.group(2)
            if unit.startswith('hour') or unit.startswith('hr'):
                result = now + timedelta(hours=amount)
            else:
                result = now + timedelta(minutes=amount)
            return to_utc(result), 0.95, f"In {amount} {unit}(s) from now"

        # Pattern: "tomorrow"
        if "tomorrow" in text_lower:
            base = now + timedelta(days=1)
            hour, minute = self._extract_time(text_lower, default_hour)
            result = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return to_utc(result), 0.95, f"Tomorrow at {hour:02d}:{minute:02d}"

        # Pattern: "today"
        if text_lower.startswith("today") or "today" in text_lower:
            hour, minute = self._extract_time(text_lower, default_hour)
            result = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return to_utc(result), 0.95, f"Today at {hour:02d}:{minute:02d}"

        # Pattern: "next week"
        if "next week" in text_lower:
            # Find next Monday
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            base = now + timedelta(days=days_until_monday)
            hour, minute = self._extract_time(text_lower, default_hour)
            result = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return to_utc(result), 0.9, f"Next week (Monday) at {hour:02d}:{minute:02d}"

        # Pattern: specific day names
        days = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6
        }
        for day_name, day_num in days.items():
            if day_name in text_lower:
                current_day = now.weekday()
                days_ahead = day_num - current_day
                if days_ahead <= 0:  # Target day already happened this week
                    days_ahead += 7
                if "next" in text_lower:
                    days_ahead += 7
                base = now + timedelta(days=days_ahead)
                hour, minute = self._extract_time(text_lower, default_hour)
                result = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
                return to_utc(result), 0.9, f"{day_name.capitalize()} at {hour:02d}:{minute:02d}"

        # Pattern: "this weekend"
        if "weekend" in text_lower:
            current_day = now.weekday()
            days_until_saturday = (5 - current_day) % 7
            if days_until_saturday == 0 and now.hour >= 12:
                days_until_saturday = 7
            base = now + timedelta(days=days_until_saturday)
            hour, minute = self._extract_time(text_lower, default_hour)
            result = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return to_utc(result), 0.85, f"This weekend (Saturday) at {hour:02d}:{minute:02d}"

        # No quick pattern matched
        return None, 0.0, ""

    def _extract_time(self, text: str, default_hour: int) -> Tuple[int, int]:
        """Extract time from text, returning (hour, minute)."""
        text_lower = text.lower()

        # Check for time of day words
        if "morning" in text_lower:
            return 9, 0
        if "noon" in text_lower:
            return 12, 0
        if "afternoon" in text_lower:
            return 14, 0
        if "evening" in text_lower:
            return 18, 0
        if "night" in text_lower:
            return 21, 0

        # Pattern: "at 3pm", "at 3:30pm", "at 15:00"
        time_patterns = [
            r'at\s+(\d{1,2}):(\d{2})\s*(am|pm)?',
            r'at\s+(\d{1,2})\s*(am|pm)',
            r'(\d{1,2}):(\d{2})\s*(am|pm)?',
            r'(\d{1,2})\s*(am|pm)',
        ]

        for pattern in time_patterns:
            match = re.search(pattern, text_lower)
            if match:
                groups = match.groups()
                hour = int(groups[0])
                minute = int(groups[1]) if len(groups) > 1 and groups[1] and groups[1].isdigit() else 0

                # Handle am/pm
                am_pm = groups[-1] if groups[-1] in ('am', 'pm') else None
                if am_pm == 'pm' and hour < 12:
                    hour += 12
                elif am_pm == 'am' and hour == 12:
                    hour = 0

                return hour, minute

        return default_hour, 0

    def _fallback_parse(
        self,
        text: str,
        now: datetime,
        context_type: str,
    ) -> Tuple[Optional[datetime], float, str]:
        """Fallback parsing when LLM fails."""
        # Try ISO format
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            # Convert to UTC for storage
            dt_utc = dt.astimezone(ZoneInfo("UTC"))
            return dt_utc, 0.95, "Parsed as ISO format"
        except ValueError:
            pass

        # Default based on context
        default_hour = 9 if context_type == "reminder" else 10 if context_type == "meeting" else 18

        # Default to tomorrow at the default hour
        result = (now + timedelta(days=1)).replace(
            hour=default_hour, minute=0, second=0, microsecond=0
        )
        # Convert to UTC for storage
        result_utc = result.astimezone(ZoneInfo("UTC"))
        return result_utc, 0.3, "Could not parse, defaulting to tomorrow"


# Singleton instance for reuse
_parser_instance: Optional[DateTimeParser] = None


def get_datetime_parser(openai_api_key: str) -> DateTimeParser:
    """Get or create the datetime parser singleton."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = DateTimeParser(openai_api_key)
    return _parser_instance
