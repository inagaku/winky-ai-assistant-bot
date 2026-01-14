"""Reminder domain model."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.utils import utc_now


class ReminderStatus(str, Enum):
    """Status of a reminder."""

    PENDING = "pending"
    SENT = "sent"
    SNOOZED = "snoozed"
    CANCELLED = "cancelled"


class Reminder(BaseModel):
    """Reminder domain model."""

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    title: str
    description: Optional[str] = None
    remind_at: datetime  # UTC
    repeat_rule: Optional[str] = None  # RRULE format for recurring reminders
    status: ReminderStatus = ReminderStatus.PENDING
    snooze_count: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @property
    def is_active(self) -> bool:
        """Check if reminder is still active."""
        return self.status in (ReminderStatus.PENDING, ReminderStatus.SNOOZED)

    @property
    def is_due(self) -> bool:
        """Check if reminder is due."""
        return self.is_active and utc_now() >= self.remind_at
