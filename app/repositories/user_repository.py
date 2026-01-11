"""User repository for data access."""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.database import Database
from app.models import User, UserPreferences

from .base_repository import BaseRepository

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository[User]):
    """Repository for User entities."""

    def __init__(self, db: Database):
        super().__init__(db)

    @property
    def table_name(self) -> str:
        return "users"

    def _row_to_model(self, row) -> User:
        """Convert a database row to a User model."""
        return User(
            id=row["id"],
            telegram_id=row["telegram_id"],
            username=row["username"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            preferences=UserPreferences(
                timezone=row["timezone"],
                language=row["language"],
                notification_enabled=row["notification_enabled"],
                daily_summary_time=row["daily_summary_time"],
            ),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _model_to_dict(self, model: User) -> dict:
        """Convert a User model to a dictionary."""
        return {
            "id": model.id,
            "telegram_id": model.telegram_id,
            "username": model.username,
            "first_name": model.first_name,
            "last_name": model.last_name,
            "timezone": model.preferences.timezone,
            "language": model.preferences.language,
            "notification_enabled": model.preferences.notification_enabled,
            "daily_summary_time": model.preferences.daily_summary_time,
            "created_at": model.created_at,
            "updated_at": model.updated_at,
        }

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get a user by their Telegram ID."""
        query = "SELECT * FROM users WHERE telegram_id = $1"
        row = await self.db.fetchrow(query, telegram_id)
        if row:
            return self._row_to_model(row)
        return None

    async def create(self, user: User) -> User:
        """Create a new user."""
        query = """
            INSERT INTO users (id, telegram_id, username, first_name, last_name,
                             timezone, language, notification_enabled, daily_summary_time,
                             created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING *
        """
        data = self._model_to_dict(user)
        row = await self.db.fetchrow(
            query,
            data["id"],
            data["telegram_id"],
            data["username"],
            data["first_name"],
            data["last_name"],
            data["timezone"],
            data["language"],
            data["notification_enabled"],
            data["daily_summary_time"],
            data["created_at"],
            data["updated_at"],
        )
        return self._row_to_model(row)

    async def update(self, user: User) -> User:
        """Update an existing user."""
        user.updated_at = datetime.utcnow()
        query = """
            UPDATE users
            SET username = $2, first_name = $3, last_name = $4,
                timezone = $5, language = $6, notification_enabled = $7,
                daily_summary_time = $8, updated_at = $9
            WHERE id = $1
            RETURNING *
        """
        data = self._model_to_dict(user)
        row = await self.db.fetchrow(
            query,
            data["id"],
            data["username"],
            data["first_name"],
            data["last_name"],
            data["timezone"],
            data["language"],
            data["notification_enabled"],
            data["daily_summary_time"],
            data["updated_at"],
        )
        return self._row_to_model(row)

    async def get_or_create(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> tuple[User, bool]:
        """Get existing user or create a new one. Returns (user, created)."""
        existing = await self.get_by_telegram_id(telegram_id)
        if existing:
            return existing, False

        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        created_user = await self.create(user)
        logger.info(f"Created new user: {telegram_id}")
        return created_user, True
