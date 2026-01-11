"""Reminder service for reminder management."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.models import Reminder, ReminderStatus
from app.repositories import ReminderRepository

from .base_service import BaseService

logger = logging.getLogger(__name__)


class ReminderService(BaseService):
    """Service for reminder management operations."""

    def __init__(self, reminder_repository: ReminderRepository):
        super().__init__()
        self.reminder_repository = reminder_repository

    async def create_reminder(
        self,
        user_id: UUID,
        title: str,
        remind_at: datetime,
        description: Optional[str] = None,
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
    ) -> Reminder:
        """Create a reminder from extracted parameters."""
        title = params.get("task") or params.get("title") or params.get("what", "Reminder")
        remind_at_str = params.get("datetime") or params.get("when") or params.get("time")

        # Parse datetime - for now use a simple approach
        # In production, use dateparser or similar
        if isinstance(remind_at_str, datetime):
            remind_at = remind_at_str
        elif remind_at_str:
            # Try to parse common formats
            remind_at = self._parse_datetime(remind_at_str)
        else:
            # Default to 1 hour from now
            remind_at = datetime.utcnow() + timedelta(hours=1)

        return await self.create_reminder(
            user_id=user_id,
            title=title,
            remind_at=remind_at,
            description=params.get("description"),
        )

    def _parse_datetime(self, dt_str: str) -> datetime:
        """Parse datetime string. Simple implementation."""
        # This is a simplified parser - in production use dateparser library
        now = datetime.utcnow()

        dt_lower = dt_str.lower()
        if "tomorrow" in dt_lower:
            base = now + timedelta(days=1)
        elif "today" in dt_lower:
            base = now
        elif "next week" in dt_lower:
            base = now + timedelta(weeks=1)
        else:
            # Try to parse as ISO format
            try:
                return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except ValueError:
                # Default to 1 hour from now
                return now + timedelta(hours=1)

        # Set default time if only date specified
        return base.replace(hour=9, minute=0, second=0, microsecond=0)

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
        return await self.reminder_repository.get_due_reminders(datetime.utcnow())

    async def mark_sent(self, reminder_id: UUID) -> Optional[Reminder]:
        """Mark a reminder as sent."""
        return await self.reminder_repository.mark_sent(reminder_id)

    async def snooze_reminder(
        self,
        reminder_id: UUID,
        minutes: int = 15,
    ) -> Optional[Reminder]:
        """Snooze a reminder for the specified minutes."""
        new_time = datetime.utcnow() + timedelta(minutes=minutes)
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

    def format_reminder_list(self, reminders: List[Reminder]) -> str:
        """Format a list of reminders for display."""
        if not reminders:
            return "You have no active reminders."

        lines = ["Your reminders:"]
        for i, reminder in enumerate(reminders, 1):
            status_emoji = "🔔" if reminder.status == ReminderStatus.PENDING else "😴"
            time_str = reminder.remind_at.strftime("%Y-%m-%d %H:%M")
            lines.append(f"{i}. {status_emoji} {reminder.title} - {time_str}")

        return "\n".join(lines)
