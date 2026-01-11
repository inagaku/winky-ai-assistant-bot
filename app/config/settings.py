"""Application settings using Pydantic."""

import os
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Telegram
    telegram_bot_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")

    # OpenAI
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")

    # Database
    database_host: str = Field(default="localhost", env="DATABASE_HOST")
    database_port: int = Field(default=5432, env="DATABASE_PORT")
    database_name: str = Field(default="winky_bot", env="DATABASE_NAME")
    database_user: str = Field(default="postgres", env="DATABASE_USER")
    database_password: str = Field(default="", env="DATABASE_PASSWORD")

    # Application
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    environment: str = Field(default="development", env="ENVIRONMENT")

    # Scheduler
    scheduler_check_interval: int = Field(
        default=60,
        env="SCHEDULER_CHECK_INTERVAL",
        description="How often to check for due notifications (seconds)",
    )

    # NLP
    confidence_threshold: float = Field(
        default=0.75,
        env="CONFIDENCE_THRESHOLD",
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
