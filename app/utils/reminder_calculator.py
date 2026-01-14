"""Smart reminder time calculator for intelligent notification scheduling."""

import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
from enum import Enum

from .time_utils import utc_now

logger = logging.getLogger(__name__)


class TimeCategory(Enum):
    """Categories of time distances for reminder calculation."""
    IMMEDIATE = "immediate"      # < 30 minutes
    VERY_SOON = "very_soon"      # 30 min - 2 hours
    SOON = "soon"                # 2 - 6 hours
    TODAY = "today"              # Same day, > 6 hours
    TOMORROW = "tomorrow"        # Next day
    THIS_WEEK = "this_week"      # 2-7 days
    NEXT_WEEK = "next_week"      # 7-14 days
    FAR_FUTURE = "far_future"    # > 14 days


class ReminderTimeCalculator:
    """
    Calculate optimal reminder/notification times based on action time.

    Smart timing rules:
    - Action in < 30 min: Notify immediately (no delay)
    - Action in 30 min - 2 hours: Notify 15 minutes before
    - Action in 2-6 hours: Notify 30 minutes before
    - Action today (> 6 hours): Notify at 16:00 (or 2 hours before if after 14:00)
    - Action tomorrow: Notify today at 16:00-18:00 (evening planning time)
    - Action in 2-7 days (this week): Notify day before at 18:00
    - Action next week: Notify on Sunday at 18:00 of current week
    - Action > 2 weeks: Notify 3 days before at 18:00

    Also considers:
    - Don't notify during sleep hours (22:00 - 08:00)
    - Prefer notification at natural break times (9:00, 12:00, 16:00, 18:00)
    """

    # Configurable thresholds
    SLEEP_START_HOUR = 22
    SLEEP_END_HOUR = 8

    # Natural break times for notifications (preferred hours)
    PREFERRED_HOURS = [9, 12, 16, 18]

    # Evening planning time - when to remind about next day's tasks
    EVENING_REMINDER_HOUR = 18

    # Afternoon reminder time for same-day tasks
    AFTERNOON_REMINDER_HOUR = 16

    def __init__(
        self,
        sleep_start: int = 22,
        sleep_end: int = 8,
        evening_hour: int = 18,
        afternoon_hour: int = 16,
    ):
        self.sleep_start = sleep_start
        self.sleep_end = sleep_end
        self.evening_hour = evening_hour
        self.afternoon_hour = afternoon_hour

    def calculate_reminder_time(
        self,
        action_time: datetime,
        reference_time: Optional[datetime] = None,
        item_type: str = "reminder",  # "reminder", "task", "meeting"
    ) -> Tuple[datetime, str]:
        """
        Calculate the optimal reminder notification time.

        Args:
            action_time: When the action/event occurs
            reference_time: Current time (defaults to now)
            item_type: Type of item (affects timing slightly)

        Returns:
            Tuple of (reminder_time, explanation)
        """
        now = reference_time or utc_now()
        time_until = action_time - now
        category = self._categorize_time_distance(time_until, now, action_time)

        reminder_time, explanation = self._calculate_by_category(
            category, action_time, now, item_type
        )

        # Ensure reminder time is not in sleep hours
        reminder_time = self._adjust_for_sleep_hours(reminder_time)

        # Ensure reminder time is not in the past
        if reminder_time < now:
            reminder_time = now + timedelta(minutes=1)
            explanation = "Immediate notification (already due)"

        # Ensure reminder time is before action time
        if reminder_time >= action_time:
            # Notify at least 5 minutes before for meetings, immediately for others
            buffer = timedelta(minutes=5) if item_type == "meeting" else timedelta(minutes=1)
            reminder_time = action_time - buffer
            if reminder_time < now:
                reminder_time = now + timedelta(minutes=1)
            explanation = f"Notification just before {item_type}"

        return reminder_time, explanation

    def _categorize_time_distance(
        self,
        time_until: timedelta,
        now: datetime,
        action_time: datetime,
    ) -> TimeCategory:
        """Categorize the time distance for reminder calculation."""
        hours = time_until.total_seconds() / 3600
        days = time_until.days

        if hours < 0.5:
            return TimeCategory.IMMEDIATE
        elif hours < 2:
            return TimeCategory.VERY_SOON
        elif hours < 6:
            return TimeCategory.SOON
        elif now.date() == action_time.date():
            return TimeCategory.TODAY
        elif (action_time.date() - now.date()).days == 1:
            return TimeCategory.TOMORROW
        elif days < 7:
            return TimeCategory.THIS_WEEK
        elif days < 14:
            return TimeCategory.NEXT_WEEK
        else:
            return TimeCategory.FAR_FUTURE

    def _calculate_by_category(
        self,
        category: TimeCategory,
        action_time: datetime,
        now: datetime,
        item_type: str,
    ) -> Tuple[datetime, str]:
        """Calculate reminder time based on category."""

        if category == TimeCategory.IMMEDIATE:
            # Notify immediately
            return now + timedelta(minutes=1), "Immediate - action is very soon"

        elif category == TimeCategory.VERY_SOON:
            # 15 minutes before
            reminder = action_time - timedelta(minutes=15)
            return reminder, "15 minutes before (action in 30 min - 2 hours)"

        elif category == TimeCategory.SOON:
            # 30 minutes before
            reminder = action_time - timedelta(minutes=30)
            return reminder, "30 minutes before (action in 2-6 hours)"

        elif category == TimeCategory.TODAY:
            # Same day, notify at 16:00 or 2 hours before
            today_afternoon = now.replace(
                hour=self.afternoon_hour, minute=0, second=0, microsecond=0
            )

            if action_time.hour >= 18:
                # Evening action - notify at afternoon
                if now.hour < self.afternoon_hour:
                    return today_afternoon, f"Today at {self.afternoon_hour}:00 (evening action)"
                else:
                    # Already past afternoon, notify 2 hours before
                    reminder = action_time - timedelta(hours=2)
                    return reminder, "2 hours before (same day evening)"
            else:
                # Afternoon action - notify 2 hours before
                reminder = action_time - timedelta(hours=2)
                return reminder, "2 hours before (same day)"

        elif category == TimeCategory.TOMORROW:
            # Tomorrow - notify today evening
            today_evening = now.replace(
                hour=self.evening_hour, minute=0, second=0, microsecond=0
            )

            if now.hour < self.evening_hour:
                return today_evening, f"Today at {self.evening_hour}:00 (action tomorrow)"
            else:
                # Already evening, notify now + 30 min
                reminder = now + timedelta(minutes=30)
                return reminder, "Soon (tomorrow's action, already evening)"

        elif category == TimeCategory.THIS_WEEK:
            # This week - notify the day before at 18:00
            day_before = (action_time - timedelta(days=1)).replace(
                hour=self.evening_hour, minute=0, second=0, microsecond=0
            )
            return day_before, f"Day before at {self.evening_hour}:00"

        elif category == TimeCategory.NEXT_WEEK:
            # Next week - notify on Sunday evening of current week
            days_until_sunday = (6 - now.weekday()) % 7
            if days_until_sunday == 0 and now.hour >= self.evening_hour:
                # Already Sunday evening, notify tomorrow
                sunday = now + timedelta(days=1)
            else:
                sunday = now + timedelta(days=days_until_sunday)

            sunday_evening = sunday.replace(
                hour=self.evening_hour, minute=0, second=0, microsecond=0
            )

            # Make sure Sunday is before the action
            if sunday_evening >= action_time:
                # Fall back to day before
                day_before = (action_time - timedelta(days=1)).replace(
                    hour=self.evening_hour, minute=0, second=0, microsecond=0
                )
                return day_before, f"Day before at {self.evening_hour}:00"

            return sunday_evening, f"Sunday at {self.evening_hour}:00 (next week's action)"

        else:  # FAR_FUTURE
            # Far future - notify 3 days before at 18:00
            three_days_before = (action_time - timedelta(days=3)).replace(
                hour=self.evening_hour, minute=0, second=0, microsecond=0
            )
            return three_days_before, f"3 days before at {self.evening_hour}:00"

    def _adjust_for_sleep_hours(self, reminder_time: datetime) -> datetime:
        """Adjust reminder time to avoid sleep hours."""
        hour = reminder_time.hour

        if hour >= self.sleep_start or hour < self.sleep_end:
            # In sleep hours - move to next morning or previous evening
            if hour >= self.sleep_start:
                # Late night - move to next morning
                next_day = reminder_time + timedelta(days=1)
                return next_day.replace(
                    hour=self.sleep_end, minute=0, second=0, microsecond=0
                )
            else:
                # Early morning - move to wake time
                return reminder_time.replace(
                    hour=self.sleep_end, minute=0, second=0, microsecond=0
                )

        return reminder_time

    def get_time_until_action(
        self,
        action_time: datetime,
        reference_time: Optional[datetime] = None,
    ) -> str:
        """Get a human-readable string of time until action."""
        now = reference_time or utc_now()
        time_until = action_time - now

        if time_until.total_seconds() < 0:
            return "overdue"

        days = time_until.days
        hours = int((time_until.total_seconds() % 86400) / 3600)
        minutes = int((time_until.total_seconds() % 3600) / 60)

        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0 and days == 0:  # Only show minutes if < 1 day
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")

        return ", ".join(parts) if parts else "now"


# Singleton instance
_calculator_instance: Optional[ReminderTimeCalculator] = None


def get_reminder_calculator() -> ReminderTimeCalculator:
    """Get or create the reminder calculator singleton."""
    global _calculator_instance
    if _calculator_instance is None:
        _calculator_instance = ReminderTimeCalculator()
    return _calculator_instance
