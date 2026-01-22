"""Meeting service for meeting management."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.models import Meeting, MeetingStatus
from app.repositories import MeetingRepository
from app.utils import DateTimeParser, utc_now, format_datetime
from app.i18n import t

from .base_service import BaseService

logger = logging.getLogger(__name__)


class MeetingService(BaseService):
    """Service for meeting management operations."""

    def __init__(self, meeting_repository: MeetingRepository, openai_api_key: str):
        super().__init__()
        self.meeting_repository = meeting_repository
        self.datetime_parser = DateTimeParser(openai_api_key)

    async def schedule_meeting(
        self,
        user_id: UUID,
        title: str,
        start_time: datetime,
        end_time: datetime,
        description: str,
        participants: Optional[List[str]] = None,
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
        user_timezone: str = "UTC",
    ) -> Meeting:
        """Create a meeting from extracted parameters."""
        title = params.get("title") or params.get("name") or params.get("subject", "Meeting")

        # Parse start time using intelligent datetime parser with user's timezone
        start_str = params.get("datetime_start") or params.get("start") or params.get("when")
        if isinstance(start_str, datetime):
            start_time = start_str
        elif start_str:
            start_time, confidence, interpretation = await self.datetime_parser.parse(
                start_str,
                timezone=user_timezone,
                context_type="meeting",
            )
            if start_time is None:
                # Default to tomorrow at 10 AM
                start_time = (utc_now() + timedelta(days=1)).replace(
                    hour=10, minute=0, second=0, microsecond=0
                )
            self.logger.info(
                f"Parsed start '{start_str}' -> {start_time} UTC (timezone: {user_timezone}, confidence: {confidence}, interpretation: {interpretation})"
            )
        else:
            # Default to tomorrow at 10 AM
            start_time = (utc_now() + timedelta(days=1)).replace(
                hour=10, minute=0, second=0, microsecond=0
            )

        # Parse end time
        end_str = params.get("datetime_end") or params.get("end")
        if isinstance(end_str, datetime):
            end_time = end_str
        elif end_str:
            end_time, confidence, interpretation = await self.datetime_parser.parse(
                end_str,
                timezone=user_timezone,
                    context_type="meeting",
            )
            if end_time is None:
                end_time = start_time + timedelta(hours=1)
            self.logger.info(
                f"Parsed end '{end_str}' -> {end_time} UTC (timezone: {user_timezone}, confidence: {confidence}, interpretation: {interpretation})"
            )
        else:
            # Default to 1 hour after start
            end_time = start_time + timedelta(hours=1)

        # Parse duration if end time not specified but duration is
        duration_str = params.get("duration")
        if duration_str and not end_str:
            duration_hours = self._parse_duration(duration_str)
            end_time = start_time + timedelta(hours=duration_hours)

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

    def _parse_duration(self, duration_str: str) -> float:
        """Parse duration string to hours."""
        duration_lower = duration_str.lower()

        # Handle "30 minutes", "1 hour", "1.5 hours", etc.
        import re

        # Match patterns like "30 min", "1 hour", "1.5 hours"
        hour_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:hour|hr)s?', duration_lower)
        if hour_match:
            return float(hour_match.group(1))

        min_match = re.search(r'(\d+)\s*(?:minute|min)s?', duration_lower)
        if min_match:
            return int(min_match.group(1)) / 60

        # Default to 1 hour
        return 1.0

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

    def format_meeting_list(
        self, meetings: List[Meeting], locale: str = "en", timezone: str = "UTC"
    ) -> str:
        """Format a list of meetings for display."""
        if not meetings:
            return t("no_meetings", locale=locale)

        lines = [t("your_meetings", locale=locale)]
        with_label = t("with", locale=locale) if locale == "ru" else "with"
        for i, meeting in enumerate(meetings, 1):
            time_str = format_datetime(meeting.start_time, locale=locale, timezone=timezone)
            duration = meeting.duration_minutes
            participants_str = ""
            if meeting.participants:
                participants_str = f" {with_label} {', '.join(meeting.participants)}"
            lines.append(f"{i}. 📅 {meeting.title}{participants_str} - {time_str} ({duration}min)")

        return "\n".join(lines)
