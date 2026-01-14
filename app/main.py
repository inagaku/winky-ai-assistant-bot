"""Main entry point for the Telegram AI Assistant Bot."""

import asyncio
import logging
import signal
import sys
import os
from typing import Optional

from telegram import Bot

from app.config import get_settings
from app.database import Database
from app.database.connection import init_database
from app.bot import TelegramBot
from app.scheduler import NotificationScheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


class Application:
    """Main application orchestrator."""

    def __init__(self):
        self.settings = get_settings()
        self.database: Optional[Database] = None
        self.bot: Optional[TelegramBot] = None
        self.scheduler: Optional[NotificationScheduler] = None
        self._shutdown_event = asyncio.Event()

    async def initialize(self) -> None:
        """Initialize all application components."""
        logger.info("Initializing application...")

        # Set log level
        logging.getLogger().setLevel(self.settings.log_level)

        # Initialize database
        self.database = init_database(
            host=self.settings.database_host,
            port=self.settings.database_port,
            database=self.settings.database_name,
            user=self.settings.database_user,
            password=self.settings.database_password,
        )
        await self.database.connect()
        logger.info("Database connected")

        # Initialize bot
        self.bot = TelegramBot(
            telegram_token=self.settings.telegram_bot_token,
            openai_api_key=self.settings.openai_api_key,
            database=self.database,
        )
        await self.bot.initialize()
        logger.info("Telegram bot initialized")

        # Initialize scheduler
        telegram_bot_instance = Bot(token=self.settings.telegram_bot_token)
        self.scheduler = NotificationScheduler(
            telegram_bot=telegram_bot_instance,
            database=self.database,
            openai_api_key=self.settings.openai_api_key,
            check_interval_seconds=self.settings.scheduler_check_interval,
        )
        logger.info("Notification scheduler initialized")

        logger.info("Application initialization complete")

    async def run(self) -> None:
        """Run the application."""
        await self.initialize()

        # Start scheduler
        await self.scheduler.start()

        # Run bot
        logger.info("Starting bot polling...")
        await self.bot.application.initialize()
        await self.bot.application.start()
        await self.bot.application.updater.start_polling()

        # Wait for shutdown signal
        await self._shutdown_event.wait()

    async def shutdown(self) -> None:
        """Shutdown the application gracefully."""
        logger.info("Shutting down application...")

        # Stop scheduler
        if self.scheduler:
            await self.scheduler.stop()

        # Stop bot
        if self.bot:
            if self.bot.application.updater.running:
                await self.bot.application.updater.stop()
            await self.bot.application.stop()
            await self.bot.application.shutdown()

        # Disconnect database
        if self.database:
            await self.database.disconnect()

        logger.info("Application shutdown complete")

    def request_shutdown(self) -> None:
        """Request application shutdown."""
        self._shutdown_event.set()


def main():
    """Main entry point."""
    app = Application()

    # Setup signal handlers
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def signal_handler():
        logger.info("Received shutdown signal")
        app.request_shutdown()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        loop.run_until_complete(app.run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        loop.run_until_complete(app.shutdown())
        loop.close()


if __name__ == "__main__":
    main()
