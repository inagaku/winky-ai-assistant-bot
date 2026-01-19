"""Application settings using Pydantic."""

import os
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Telegram
    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")

    # OpenAI
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")

    # Database
    database_host: str = Field(..., alias="WINKY_DATABASE_HOST")
    database_port: int = Field(..., alias="WINKY_DATABASE_PORT")
    database_name: str = Field(..., alias="WINKY_DATABASE_NAME")
    database_user: str = Field(..., alias="WINKY_DATABASE_USER")
    database_password: str = Field(..., alias="WINKY_DATABASE_PASSWORD")

    # Application
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    environment: str = Field(default="development", alias="ENVIRONMENT")

    # Scheduler
    scheduler_check_interval: int = Field(
        default=60,
        alias="SCHEDULER_CHECK_INTERVAL",
        description="How often to check for due notifications (seconds)",
    )

    # NLP
    intention_confidence_threshold: float = Field(
        default=0.55,
        alias="INTENTION_CONFIDENCE_THRESHOLD",
        description="Minimum confidence to execute action without clarification",
    )

    intention_low_confidence_threshold: float = Field(
        default=0.25,
        alias="INTENTION_LOW_CONFIDENCE_THRESHOLD",
        description="Minimum confidence to execute action without clarification",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @property
    def database_url(self) -> str:
        """Get the full database URL."""
        return (
            f"postgresql://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
