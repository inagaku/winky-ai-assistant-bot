"""User domain model."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.utils import utc_now


class UserPreferences(BaseModel):
    """User preferences for the assistant."""

    timezone: str = "UTC"
    language: str = "en"


class User(BaseModel):
    """User domain model."""

    id: UUID = Field(default_factory=uuid4)
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    telegram_language_code: Optional[str] = None  # Captured from Telegram API
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @property
    def display_name(self) -> str:
        """Get user's display name."""
        if self.first_name:
            return self.first_name
        if self.username:
            return f"@{self.username}"
        return f"User {self.telegram_id}"
