"""Meeting service for meeting management."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.models import Meeting, MeetingStatus
from app.repositories import MeetingRepository

from .base_service import BaseService

logger = logging.getLogger(__name__)


class MeetingService(BaseService):
    """Service for meeting management operations."""

    def __init__(self, meeting_repository: MeetingRepository):
        super().__init__()
        self.meeting_repository = meeting_repository

    async def schedule_meeting(
        self,
        user_id: UUID,
        title: str,
        start_time: datetime,
        end_time: datetime,
        participants: Optional[List[str]] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        meeting_link: Optional[str] = None,
        reminder_minutes_before: int = 15,
    ) -> Meeting:
        """Schedule a new meeting."""
        meeting = Meeting(
            user_id=user_id,
            title=title,
            description=description,
            participants=participants or [],
            start_time=start_time,
            end_time=end_time,
            location=location,
            meeting_link=meeting_link,
            reminder_minutes_before=reminder_minutes_before,
        )
        created = await self.meeting_repository.create(meeting)
        self.logger.info(f"Scheduled meeting {created.id} for user {user_id}")
        return created

    async def create_from_params(
        self,
        user_id: UUID,
        params: Dict[str, Any],
    ) -> Meeting:
        """Create a meeting from extracted parameters."""
        title = params.get("title") or params.get("meeting") or params.get("subject", "Meeting")

        # Parse start time
        start_str = params.get("datetime_start") or params.get("start") or params.get("when")
        if isinstance(start_str, datetime):
            start_time = start_str
        elif start_str:
            start_time = self._parse_datetime(start_str)
        else:
            # Default to tomorrow at 10 AM
            start_time = (datetime.utcnow() + timedelta(days=1)).replace(
                hour=10, minute=0, second=0, microsecond=0
            )

        # Parse end time
        end_str = params.get("datetime_end") or params.get("end")
        if isinstance(end_str, datetime):
            end_time = end_str
        elif end_str:
            end_time = self._parse_datetime(end_str)
        else:
            # Default to 1 hour after start
            end_time = start_time + timedelta(hours=1)

        # Parse participants
        participants = params.get("participants") or params.get("attendee") or []
        if isinstance(participants, str):
            participants = [p.strip() for p in participants.split(",")]

        return await self.schedule_meeting(
            user_id=user_id,
            title=title,
            start_time=start_time,
            end_time=end_time,
            participants=participants,
            description=params.get("description"),
            location=params.get("location"),
            meeting_link=params.get("meeting_link"),
        )

    def _parse_datetime(self, dt_str: str) -> datetime:
        """Parse datetime string. Simple implementation."""
        now = datetime.utcnow()

        if isinstance(dt_str, datetime):
            return dt_str

        dt_lower = dt_str.lower()
        if "tomorrow" in dt_lower:
            base = now + timedelta(days=1)
        elif "today" in dt_lower:
            base = now
        elif "next week" in dt_lower:
            base = now + timedelta(weeks=1)
        else:
            try:
                return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except ValueError:
                return now + timedelta(days=1)

        # Try to extract time from string
        if "2pm" in dt_lower or "2 pm" in dt_lower:
            return base.replace(hour=14, minute=0, second=0, microsecond=0)
        elif "3pm" in dt_lower or "3 pm" in dt_lower:
            return base.replace(hour=15, minute=0, second=0, microsecond=0)
        elif "morning" in dt_lower:
            return base.replace(hour=9, minute=0, second=0, microsecond=0)
        elif "afternoon" in dt_lower:
            return base.replace(hour=14, minute=0, second=0, microsecond=0)
        elif "evening" in dt_lower:
            return base.replace(hour=18, minute=0, second=0, microsecond=0)

        return base.replace(hour=10, minute=0, second=0, microsecond=0)

    async def get_meeting(self, meeting_id: UUID) -> Optional[Meeting]:
        """Get a meeting by ID."""
        return await self.meeting_repository.get_by_id(meeting_id)

    async def get_user_meetings(
        self,
        user_id: UUID,
        scheduled_only: bool = True,
        limit: int = 50,
    ) -> List[Meeting]:
        """Get meetings for a user."""
        if scheduled_only:
            return await self.meeting_repository.get_by_user(
                user_id, status=MeetingStatus.SCHEDULED, limit=limit
            )
        return await self.meeting_repository.get_by_user(user_id, limit=limit)

    async def get_upcoming_meetings(
        self,
        user_id: UUID,
        within_hours: int = 24,
    ) -> List[Meeting]:
        """Get upcoming meetings within a time window."""
        return await self.meeting_repository.get_upcoming(
            user_id, within_hours=within_hours
        )

    async def get_today_meetings(self, user_id: UUID) -> List[Meeting]:
        """Get all meetings for today."""
        return await self.meeting_repository.get_today_meetings(user_id)

    async def get_meetings_needing_reminder(self) -> List[Meeting]:
        """Get meetings that need reminder notifications."""
        return await self.meeting_repository.get_meetings_needing_reminder()

    async def cancel_meeting(self, meeting_id: UUID) -> Optional[Meeting]:
        """Cancel a meeting."""
        meeting = await self.meeting_repository.cancel(meeting_id)
        if meeting:
            self.logger.info(f"Meeting {meeting_id} cancelled")
        return meeting

    async def complete_meeting(self, meeting_id: UUID) -> Optional[Meeting]:
        """Mark a meeting as completed."""
        return await self.meeting_repository.complete(meeting_id)

    async def delete_meeting(self, meeting_id: UUID) -> bool:
        """Delete a meeting permanently."""
        return await self.meeting_repository.delete(meeting_id)

    async def update_meeting(
        self,
        meeting_id: UUID,
        title: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        participants: Optional[List[str]] = None,
        location: Optional[str] = None,
    ) -> Optional[Meeting]:
        """Update a meeting's fields."""
        meeting = await self.meeting_repository.get_by_id(meeting_id)
        if not meeting:
            return None

        if title is not None:
            meeting.title = title
        if start_time is not None:
            meeting.start_time = start_time
        if end_time is not None:
            meeting.end_time = end_time
        if participants is not None:
            meeting.participants = participants
        if location is not None:
            meeting.location = location

        return await self.meeting_repository.update(meeting)

    async def get_active_count(self, user_id: UUID) -> int:
        """Get count of scheduled meetings for a user."""
        return await self.meeting_repository.get_active_count(user_id)

    def format_meeting_list(self, meetings: List[Meeting]) -> str:
        """Format a list of meetings for display."""
        if not meetings:
            return "You have no upcoming meetings."

        lines = ["Your meetings:"]
        for i, meeting in enumerate(meetings, 1):
            time_str = meeting.start_time.strftime("%Y-%m-%d %H:%M")
            duration = meeting.duration_minutes
            participants_str = ""
            if meeting.participants:
                participants_str = f" with {', '.join(meeting.participants)}"
            lines.append(f"{i}. 📅 {meeting.title}{participants_str} - {time_str} ({duration}min)")

        return "\n".join(lines)
