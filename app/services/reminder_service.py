"""Reminder service for reminder management."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.models import Reminder, ReminderStatus
from app.repositories import ReminderRepository
from app.utils import DateTimeParser, ReminderTimeCalculator, utc_now, format_datetime
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
        """Create a reminder from extracted parameters."""
        title = params.get("title") or params.get("name") or params.get("what", "Reminder")
        action_time_str = params.get("datetime") or params.get("when") or params.get("time")

        # Parse the action datetime (when the thing happens, not when to remind)
        if isinstance(action_time_str, datetime):
            action_time = action_time_str
        elif action_time_str:
            # Use intelligent datetime parser with user's timezone
            action_time, confidence, interpretation = await self.datetime_parser.parse(
                action_time_str,
                timezone=user_timezone,
                context_type="reminder",
            )
            if action_time is None:
                # Fallback to 1 hour from now
                action_time = utc_now() + timedelta(hours=1)
            self.logger.info(
                f"Parsed '{action_time_str}' -> {action_time} UTC (timezone: {user_timezone}, confidence: {confidence}, interpretation: {interpretation})"
            )
        else:
            # Default to 1 hour from now
            action_time = utc_now() + timedelta(hours=1)

        # Calculate smart reminder time
        remind_at, explanation = self.reminder_calculator.calculate_reminder_time(
            action_time=action_time,
            item_type="reminder",
        )
        self.logger.info(f"Smart reminder time: {remind_at} ({explanation})")

        # Build description with action time if not provided
        description = params.get("description") or ""
        if action_time != remind_at:
            # Include the actual action time in the description for context
            time_until = self.reminder_calculator.get_time_until_action(action_time)
            if not description:
                description = f"Action scheduled for {action_time.strftime('%Y-%m-%d %H:%M')} ({time_until})"

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
        """Get reminders for a user."""
        if active_only:
            return await self.reminder_repository.get_by_user(
                user_id, status=ReminderStatus.PENDING, limit=limit
            )
        return await self.reminder_repository.get_by_user(user_id, limit=limit)

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
