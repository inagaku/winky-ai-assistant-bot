"""User repository for data access."""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.database import Database
from app.models import User, UserPreferences
from app.utils import utc_now

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
            telegram_language_code=row.get("telegram_language_code"),
            preferences=UserPreferences(
                timezone=row["timezone"],
                language=row["language"],
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
            "telegram_language_code": model.telegram_language_code,
            "timezone": model.preferences.timezone,
            "language": model.preferences.language,
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
                             telegram_language_code, timezone, language,
                             created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
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
            data["telegram_language_code"],
            data["timezone"],
            data["language"],
            data["created_at"],
            data["updated_at"],
        )
        return self._row_to_model(row)

    async def update(self, user: User) -> User:
        """Update an existing user."""
        user.updated_at = utc_now()
        query = """
            UPDATE users
            SET username = $2, first_name = $3, last_name = $4,
                telegram_language_code = $5, timezone = $6, language = $7,
                updated_at = $8
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
            data["telegram_language_code"],
            data["timezone"],
            data["language"],
            data["updated_at"],
        )
        return self._row_to_model(row)

    async def get_or_create(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        language_code: Optional[str] = None,
    ) -> tuple[User, bool]:
        """Get existing user or create a new one. Returns (user, created)."""
        existing = await self.get_by_telegram_id(telegram_id)
        if existing:
            # Update language_code if changed
            if language_code and existing.telegram_language_code != language_code:
                existing.telegram_language_code = language_code
                await self.update(existing)
            return existing, False

        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            telegram_language_code=language_code,
        )
        created_user = await self.create(user)
        logger.info(f"Created new user: {telegram_id} (lang: {language_code})")
        return created_user, True
