"""User domain model."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class UserPreferences(BaseModel):
    """User preferences for the assistant."""

    timezone: str = "UTC"
    language: str = "en"
    notification_enabled: bool = True
    daily_summary_time: Optional[str] = None  # HH:MM format


class User(BaseModel):
    """User domain model."""

    id: UUID = Field(default_factory=uuid4)
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def display_name(self) -> str:
        """Get user's display name."""
        if self.first_name:
            return self.first_name
        if self.username:
            return f"@{self.username}"
        return f"User {self.telegram_id}"
