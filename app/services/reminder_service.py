"""Reminder service for reminder management."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.models import Reminder, ReminderStatus
from app.repositories import ReminderRepository
from app.utils import DateTimeParser, ReminderTimeCalculator, utc_now, format_datetime, parse_duration
from app.i18n import t

from .base_service import BaseService

logger = logging.getLogger(__name__)


class ReminderService(BaseService):
    """Service for reminder management operations."""

    def __init__(self, reminder_repository: ReminderRepository, openai_api_key: str):
        super().__init__()
        self.reminder_repository = reminder_repository
        self.datetime_parser = DateTimeParser(openai_api_key)
        self.reminder_calculator = ReminderTimeCalculator()

    async def create_reminder(
        self,
        user_id: UUID,
        title: str,
        remind_at: datetime,
        description: str,
        repeat_rule: Optional[str] = None,
    ) -> Reminder:
        """Create a new reminder."""
        reminder = Reminder(
            user_id=user_id,
            title=title,
            description=description,
            remind_at=remind_at,
            repeat_rule=repeat_rule,
        )
        created = await self.reminder_repository.create(reminder)
        self.logger.info(f"Created reminder {created.id} for user {user_id}")
        return created

    async def create_from_params(
        self,
        user_id: UUID,
        params: Dict[str, Any],
        user_timezone: str = "UTC",
    ) -> Reminder:
        """
        Create a reminder from extracted parameters.

        Supports three modes:
        1. Explicit notification time: "remind me AT 4pm" -> remind_at_explicit
        2. Event time with lead: "meeting at 4pm, notify 1h before" -> event_time + lead_time
        3. Event time only: "meeting at 4pm" -> event_time (uses smart calculator)
        """
        title = params.get("title") or params.get("name") or params.get("what", "Reminder")
        description = params.get("description") or ""

        # Extract time parameters
        remind_at_explicit_str = params.get("remind_at_explicit")
        event_time_str = params.get("event_time") or params.get("datetime") or params.get("when") or params.get("time")
        lead_time_str = params.get("lead_time")

        remind_at = None
        event_time = None
        explanation = ""

        # Case 1: Explicit notification time - user said "remind me AT <time>"
        if remind_at_explicit_str:
            remind_at, confidence, interpretation = await self.datetime_parser.parse(
                remind_at_explicit_str,
                timezone=user_timezone,
                context_type="reminder",
            )
            if remind_at:
                explanation = f"Explicit notification time: {interpretation}"
                self.logger.info(f"Using explicit remind_at: '{remind_at_explicit_str}' -> {remind_at} UTC ({explanation})")

        # Case 2 & 3: Event time provided
        if remind_at is None and event_time_str:
            # Parse event time
            if isinstance(event_time_str, datetime):
                event_time = event_time_str
            else:
                event_time, confidence, interpretation = await self.datetime_parser.parse(
                    event_time_str,
                    timezone=user_timezone,
                    context_type="reminder",
                )
                if event_time:
                    self.logger.info(f"Parsed event_time: '{event_time_str}' -> {event_time} UTC ({interpretation})")

            if event_time:
                # Case 2: Event time with lead time
                if lead_time_str:
                    lead_minutes = parse_duration(lead_time_str)
                    if lead_minutes:
                        remind_at = event_time - timedelta(minutes=lead_minutes)
                        explanation = f"{lead_minutes} minutes before event at {event_time.strftime('%H:%M')}"
                        self.logger.info(f"Using lead time: {lead_time_str} ({lead_minutes}min) -> remind_at={remind_at}")

                # Case 3: Event time only - use smart calculator
                if remind_at is None:
                    remind_at, explanation = self.reminder_calculator.calculate_reminder_time(
                        action_time=event_time,
                        item_type="reminder",
                    )
                    self.logger.info(f"Smart reminder time: {remind_at} ({explanation})")

        # Case 4: No time specified - default to 1 hour from now
        if remind_at is None:
            remind_at = utc_now() + timedelta(hours=1)
            explanation = "Default: 1 hour from now"
            self.logger.info(f"No time specified, defaulting to {remind_at}")

        # Build description with event time context if applicable
        if event_time and event_time != remind_at and not description:
            time_until = self.reminder_calculator.get_time_until_action(event_time)
            description = f"Event at {event_time.strftime('%Y-%m-%d %H:%M')} ({time_until})"

        return await self.create_reminder(
            user_id=user_id,
            title=title,
            remind_at=remind_at,
            description=description,
        )

    async def get_reminder(self, reminder_id: UUID) -> Optional[Reminder]:
        """Get a reminder by ID."""
        return await self.reminder_repository.get_by_id(reminder_id)

    async def get_user_reminders(
        self,
        user_id: UUID,
        active_only: bool = True,
        limit: int = 50,
    ) -> List[Reminder]:
        """Get reminders for a user (active = pending + snoozed)."""
        return await self.reminder_repository.get_by_user(
            user_id, active_only=active_only, limit=limit
        )

    async def get_due_reminders(self) -> List[Reminder]:
        """Get all reminders that are due."""
        return await self.reminder_repository.get_due_reminders(utc_now())

    async def mark_sent(self, reminder_id: UUID) -> Optional[Reminder]:
        """Mark a reminder as sent."""
        return await self.reminder_repository.mark_sent(reminder_id)

    async def snooze_reminder(
        self,
        reminder_id: UUID,
        minutes: int = 15,
    ) -> Optional[Reminder]:
        """Snooze a reminder for the specified minutes."""
        new_time = utc_now() + timedelta(minutes=minutes)
        return await self.reminder_repository.snooze(reminder_id, new_time)

    async def cancel_reminder(self, reminder_id: UUID) -> Optional[Reminder]:
        """Cancel a reminder."""
        return await self.reminder_repository.cancel(reminder_id)

    async def delete_reminder(self, reminder_id: UUID) -> bool:
        """Delete a reminder permanently."""
        return await self.reminder_repository.delete(reminder_id)

    async def update_remind_at(
        self,
        reminder_id: UUID,
        new_time: datetime,
    ) -> Optional[Reminder]:
        """Update the reminder time."""
        reminder = await self.reminder_repository.get_by_id(reminder_id)
        if not reminder:
            return None

        reminder.remind_at = new_time
        # Reset to pending if it was snoozed or sent
        if reminder.status in (ReminderStatus.SNOOZED, ReminderStatus.SENT):
            reminder.status = ReminderStatus.PENDING

        updated = await self.reminder_repository.update(reminder)
        self.logger.info(f"Updated reminder {reminder_id} time to {new_time}")
        return updated

    async def update_title(
        self,
        reminder_id: UUID,
        new_title: str,
    ) -> Optional[Reminder]:
        """Update the reminder title."""
        reminder = await self.reminder_repository.get_by_id(reminder_id)
        if not reminder:
            return None

        reminder.title = new_title
        updated = await self.reminder_repository.update(reminder)
        self.logger.info(f"Updated reminder {reminder_id} title to '{new_title}'")
        return updated

    async def adjust_time(
        self,
        reminder_id: UUID,
        minutes_delta: int,
    ) -> Optional[Reminder]:
        """Adjust reminder time by a number of minutes (positive = later, negative = earlier)."""
        reminder = await self.reminder_repository.get_by_id(reminder_id)
        if not reminder:
            return None

        new_time = reminder.remind_at + timedelta(minutes=minutes_delta)
        return await self.update_remind_at(reminder_id, new_time)

    async def get_active_count(self, user_id: UUID) -> int:
        """Get count of active reminders for a user."""
        return await self.reminder_repository.get_active_count(user_id)

    def format_reminder_list(
        self, reminders: List[Reminder], locale: str = "en", timezone: str = "UTC"
    ) -> str:
        """Format a list of reminders for display."""
        if not reminders:
            return t("no_reminders", locale=locale)

        lines = [t("your_reminders", locale=locale)]
        for i, reminder in enumerate(reminders, 1):
            status_emoji = "🔔" if reminder.status == ReminderStatus.PENDING else "😴"
            time_str = format_datetime(reminder.remind_at, locale=locale, timezone=timezone)
            lines.append(f"{i}. {status_emoji} {reminder.title} - {time_str}")

        return "\n".join(lines)
