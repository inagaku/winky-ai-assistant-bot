"""Meeting repository for data access."""

import logging
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from app.database import Database
from app.models import Meeting, MeetingStatus

from .base_repository import BaseRepository

logger = logging.getLogger(__name__)


class MeetingRepository(BaseRepository[Meeting]):
    """Repository for Meeting entities."""

    def __init__(self, db: Database):
        super().__init__(db)

    @property
    def table_name(self) -> str:
        return "meetings"

    def _row_to_model(self, row) -> Meeting:
        """Convert a database row to a Meeting model."""
        return Meeting(
            id=row["id"],
            user_id=row["user_id"],
            title=row["title"],
            description=row["description"],
            participants=row["participants"] or [],
            start_time=row["start_time"],
            end_time=row["end_time"],
            location=row["location"],
            meeting_link=row["meeting_link"],
            status=MeetingStatus(row["status"]),
            reminder_minutes_before=row["reminder_minutes_before"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _model_to_dict(self, model: Meeting) -> dict:
        """Convert a Meeting model to a dictionary."""
        return {
            "id": model.id,
            "user_id": model.user_id,
            "title": model.title,
            "description": model.description,
            "participants": model.participants,
            "start_time": model.start_time,
            "end_time": model.end_time,
            "location": model.location,
            "meeting_link": model.meeting_link,
            "status": model.status.value,
            "reminder_minutes_before": model.reminder_minutes_before,
            "created_at": model.created_at,
            "updated_at": model.updated_at,
        }

    async def create(self, meeting: Meeting) -> Meeting:
        """Create a new meeting."""
        query = """
            INSERT INTO meetings (id, user_id, title, description, participants,
                                 start_time, end_time, location, meeting_link,
                                 status, reminder_minutes_before, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            RETURNING *
        """
        data = self._model_to_dict(meeting)
        row = await self.db.fetchrow(
            query,
            data["id"],
            data["user_id"],
            data["title"],
            data["description"],
            data["participants"],
            data["start_time"],
            data["end_time"],
            data["location"],
            data["meeting_link"],
            data["status"],
            data["reminder_minutes_before"],
            data["created_at"],
            data["updated_at"],
        )
        return self._row_to_model(row)

    async def update(self, meeting: Meeting) -> Meeting:
        """Update an existing meeting."""
        meeting.updated_at = datetime.utcnow()
        query = """
            UPDATE meetings
            SET title = $2, description = $3, participants = $4, start_time = $5,
                end_time = $6, location = $7, meeting_link = $8, status = $9,
                reminder_minutes_before = $10, updated_at = $11
            WHERE id = $1
            RETURNING *
        """
        data = self._model_to_dict(meeting)
        row = await self.db.fetchrow(
            query,
            data["id"],
            data["title"],
            data["description"],
            data["participants"],
            data["start_time"],
            data["end_time"],
            data["location"],
            data["meeting_link"],
            data["status"],
            data["reminder_minutes_before"],
            data["updated_at"],
        )
        return self._row_to_model(row)

    async def get_by_user(
        self,
        user_id: UUID,
        status: Optional[MeetingStatus] = None,
        limit: int = 50,
    ) -> List[Meeting]:
        """Get meetings for a user."""
        if status:
            query = """
                SELECT * FROM meetings
                WHERE user_id = $1 AND status = $2
                ORDER BY start_time ASC
                LIMIT $3
            """
            rows = await self.db.fetch(query, user_id, status.value, limit)
        else:
            query = """
                SELECT * FROM meetings
                WHERE user_id = $1
                ORDER BY start_time ASC
                LIMIT $2
            """
            rows = await self.db.fetch(query, user_id, limit)
        return [self._row_to_model(row) for row in rows]

    async def get_upcoming(
        self,
        user_id: UUID,
        within_hours: int = 24,
        limit: int = 10,
    ) -> List[Meeting]:
        """Get upcoming meetings within a time window."""
        now = datetime.utcnow()
        end_time = now + timedelta(hours=within_hours)
        query = """
            SELECT * FROM meetings
            WHERE user_id = $1
                AND status = 'scheduled'
                AND start_time BETWEEN $2 AND $3
            ORDER BY start_time ASC
            LIMIT $4
        """
        rows = await self.db.fetch(query, user_id, now, end_time, limit)
        return [self._row_to_model(row) for row in rows]

    async def get_meetings_needing_reminder(self) -> List[Meeting]:
        """Get meetings that need reminder notifications sent."""
        now = datetime.utcnow()
        query = """
            SELECT * FROM meetings
            WHERE status = 'scheduled'
                AND start_time > $1
                AND start_time <= $1 + (reminder_minutes_before || ' minutes')::interval
            ORDER BY start_time ASC
        """
        rows = await self.db.fetch(query, now)
        return [self._row_to_model(row) for row in rows]

    async def get_today_meetings(self, user_id: UUID) -> List[Meeting]:
        """Get all meetings for today."""
        now = datetime.utcnow()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        query = """
            SELECT * FROM meetings
            WHERE user_id = $1
                AND start_time >= $2
                AND start_time < $3
            ORDER BY start_time ASC
        """
        rows = await self.db.fetch(query, user_id, start_of_day, end_of_day)
        return [self._row_to_model(row) for row in rows]

    async def cancel(self, meeting_id: UUID) -> Optional[Meeting]:
        """Cancel a meeting."""
        query = """
            UPDATE meetings
            SET status = 'cancelled', updated_at = $2
            WHERE id = $1
            RETURNING *
        """
        row = await self.db.fetchrow(query, meeting_id, datetime.utcnow())
        if row:
            return self._row_to_model(row)
        return None

    async def complete(self, meeting_id: UUID) -> Optional[Meeting]:
        """Mark a meeting as completed."""
        query = """
            UPDATE meetings
            SET status = 'completed', updated_at = $2
            WHERE id = $1
            RETURNING *
        """
        row = await self.db.fetchrow(query, meeting_id, datetime.utcnow())
        if row:
            return self._row_to_model(row)
        return None

    async def get_active_count(self, user_id: UUID) -> int:
        """Get count of scheduled meetings for a user."""
        query = """
            SELECT COUNT(*) FROM meetings
            WHERE user_id = $1 AND status = 'scheduled'
        """
        return await self.db.fetchval(query, user_id)
