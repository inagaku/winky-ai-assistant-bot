"""User service for user management."""

import logging
from typing import Optional
from uuid import UUID

from app.models import User, UserPreferences
from app.repositories import UserRepository

from .base_service import BaseService

logger = logging.getLogger(__name__)


class UserService(BaseService):
    """Service for user management operations."""

    def __init__(self, user_repository: UserRepository):
        super().__init__()
        self.user_repository = user_repository

    async def get_or_create_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        language_code: Optional[str] = None,
    ) -> User:
        """Get existing user or create a new one."""
        user, created = await self.user_repository.get_or_create(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code,
        )
        if created:
            self.logger.info(f"New user registered: {telegram_id} (lang: {language_code})")
        return user

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID."""
        return await self.user_repository.get_by_telegram_id(telegram_id)

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by internal UUID."""
        return await self.user_repository.get_by_id(user_id)

    async def update_preferences(
        self,
        user_id: UUID,
        preferences: UserPreferences,
    ) -> Optional[User]:
        """Update user preferences."""
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            return None

        user.preferences = preferences
        return await self.user_repository.update(user)

    async def update_timezone(self, user_id: UUID, timezone: str) -> Optional[User]:
        """Update user's timezone."""
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            return None

        user.preferences.timezone = timezone
        return await self.user_repository.update(user)

    async def update_language(self, user_id: UUID, language: str) -> Optional[User]:
        """Update user's language preference."""
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            return None

        user.preferences.language = language
        return await self.user_repository.update(user)
