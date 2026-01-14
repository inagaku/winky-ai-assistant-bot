"""Reminder repository for data access."""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from app.database import Database
from app.models import Reminder, ReminderStatus
from app.utils import utc_now

from .base_repository import BaseRepository

logger = logging.getLogger(__name__)


class ReminderRepository(BaseRepository[Reminder]):
    """Repository for Reminder entities."""

    def __init__(self, db: Database):
        super().__init__(db)

    @property
    def table_name(self) -> str:
        return "reminders"

    def _row_to_model(self, row) -> Reminder:
        """Convert a database row to a Reminder model."""
        return Reminder(
            id=row["id"],
            user_id=row["user_id"],
            title=row["title"],
            description=row["description"],
            remind_at=row["remind_at"],
            repeat_rule=row["repeat_rule"],
            status=ReminderStatus(row["status"]),
            snooze_count=row["snooze_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _model_to_dict(self, model: Reminder) -> dict:
        """Convert a Reminder model to a dictionary."""
        return {
            "id": model.id,
            "user_id": model.user_id,
            "title": model.title,
            "description": model.description,
            "remind_at": model.remind_at,
            "repeat_rule": model.repeat_rule,
            "status": model.status.value,
            "snooze_count": model.snooze_count,
            "created_at": model.created_at,
            "updated_at": model.updated_at,
        }

    async def create(self, reminder: Reminder) -> Reminder:
        """Create a new reminder."""
        query = """
            INSERT INTO reminders (id, user_id, title, description, remind_at,
                                  repeat_rule, status, snooze_count, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING *
        """
        data = self._model_to_dict(reminder)
        row = await self.db.fetchrow(
            query,
            data["id"],
            data["user_id"],
            data["title"],
            data["description"],
            data["remind_at"],
            data["repeat_rule"],
            data["status"],
            data["snooze_count"],
            data["created_at"],
            data["updated_at"],
        )
        return self._row_to_model(row)

    async def update(self, reminder: Reminder) -> Reminder:
        """Update an existing reminder."""
        reminder.updated_at = utc_now()
        query = """
            UPDATE reminders
            SET title = $2, description = $3, remind_at = $4, repeat_rule = $5,
                status = $6, snooze_count = $7, updated_at = $8
            WHERE id = $1
            RETURNING *
        """
        data = self._model_to_dict(reminder)
        row = await self.db.fetchrow(
            query,
            data["id"],
            data["title"],
            data["description"],
            data["remind_at"],
            data["repeat_rule"],
            data["status"],
            data["snooze_count"],
            data["updated_at"],
        )
        return self._row_to_model(row)

    async def get_by_user(
        self,
        user_id: UUID,
        status: Optional[ReminderStatus] = None,
        active_only: bool = False,
        limit: int = 50,
    ) -> List[Reminder]:
        """Get reminders for a user, optionally filtered by status."""
        if active_only:
            # Active means pending or snoozed
            query = """
                SELECT * FROM reminders
                WHERE user_id = $1 AND status IN ('pending', 'snoozed')
                ORDER BY remind_at ASC
                LIMIT $2
            """
            rows = await self.db.fetch(query, user_id, limit)
        elif status:
            query = """
                SELECT * FROM reminders
                WHERE user_id = $1 AND status = $2
                ORDER BY remind_at ASC
                LIMIT $3
            """
            rows = await self.db.fetch(query, user_id, status.value, limit)
        else:
            query = """
                SELECT * FROM reminders
                WHERE user_id = $1
                ORDER BY remind_at ASC
                LIMIT $2
            """
            rows = await self.db.fetch(query, user_id, limit)
        return [self._row_to_model(row) for row in rows]

    async def get_due_reminders(self, before: datetime) -> List[Reminder]:
        """Get all active reminders due before the given time (pending or snoozed)."""
        query = """
            SELECT * FROM reminders
            WHERE status IN ('pending', 'snoozed') AND remind_at <= $1
            ORDER BY remind_at ASC
        """
        rows = await self.db.fetch(query, before)
        return [self._row_to_model(row) for row in rows]

    async def mark_sent(self, reminder_id: UUID) -> Optional[Reminder]:
        """Mark a reminder as sent."""
        query = """
            UPDATE reminders
            SET status = 'sent', updated_at = $2
            WHERE id = $1
            RETURNING *
        """
        row = await self.db.fetchrow(query, reminder_id, utc_now())
        if row:
            return self._row_to_model(row)
        return None

    async def snooze(self, reminder_id: UUID, new_time: datetime) -> Optional[Reminder]:
        """Snooze a reminder to a new time."""
        query = """
            UPDATE reminders
            SET remind_at = $2, status = 'snoozed', snooze_count = snooze_count + 1, updated_at = $3
            WHERE id = $1
            RETURNING *
        """
        row = await self.db.fetchrow(query, reminder_id, new_time, utc_now())
        if row:
            return self._row_to_model(row)
        return None

    async def cancel(self, reminder_id: UUID) -> Optional[Reminder]:
        """Cancel a reminder."""
        query = """
            UPDATE reminders
            SET status = 'cancelled', updated_at = $2
            WHERE id = $1
            RETURNING *
        """
        row = await self.db.fetchrow(query, reminder_id, utc_now())
        if row:
            return self._row_to_model(row)
        return None

    async def get_active_count(self, user_id: UUID) -> int:
        """Get count of active reminders for a user."""
        query = """
            SELECT COUNT(*) FROM reminders
            WHERE user_id = $1 AND status IN ('pending', 'snoozed')
        """
        return await self.db.fetchval(query, user_id)
