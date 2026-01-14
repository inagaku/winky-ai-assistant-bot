"""Meeting domain model."""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.utils import utc_now


class MeetingStatus(str, Enum):
    """Status of a meeting."""

    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Meeting(BaseModel):
    """Meeting domain model."""

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    title: str
    description: Optional[str] = None
    participants: List[str] = Field(default_factory=list)
    start_time: datetime  # UTC
    end_time: datetime  # UTC
    location: Optional[str] = None
    meeting_link: Optional[str] = None
    status: MeetingStatus = MeetingStatus.SCHEDULED
    reminder_minutes_before: int = 15  # Minutes before meeting to send reminder
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def duration_minutes(self) -> int:
        """Get meeting duration in minutes."""
        delta = self.end_time - self.start_time
        return int(delta.total_seconds() / 60)

    @property
    def is_active(self) -> bool:
        """Check if meeting is still active."""
        return self.status in (MeetingStatus.SCHEDULED, MeetingStatus.IN_PROGRESS)

    @property
    def is_upcoming(self) -> bool:
        """Check if meeting is in the future."""
        return self.is_active and self.start_time > utc_now()
