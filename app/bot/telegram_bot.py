"""Main Telegram bot application."""

import logging
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler as TelegramCommandHandler,
    MessageHandler as TelegramMessageHandler,
    CallbackQueryHandler,
    filters,
)

from app.database import Database
from app.repositories import (
    UserRepository,
    ReminderRepository,
    TaskRepository,
    MeetingRepository,
)
from app.services import (
    UserService,
    ReminderService,
    TaskService,
    MeetingService,
    AssistantService,
)
from app.intelligence import IntentResolver

from .handlers import CommandHandler, MessageHandler, CallbackHandler

logger = logging.getLogger(__name__)


class TelegramBot:
    """Main Telegram bot application."""

    def __init__(
        self,
        telegram_token: str,
        openai_api_key: str,
        database: Database,
    ):
        self.telegram_token = telegram_token
        self.openai_api_key = openai_api_key
        self.database = database

        # Initialize repositories
        self.user_repository = UserRepository(database)
        self.reminder_repository = ReminderRepository(database)
        self.task_repository = TaskRepository(database)
        self.meeting_repository = MeetingRepository(database)

        # Initialize services
        self.user_service = UserService(self.user_repository)
        self.reminder_service = ReminderService(self.reminder_repository)
        self.task_service = TaskService(self.task_repository)
        self.meeting_service = MeetingService(self.meeting_repository)
        self.assistant_service = AssistantService(
            user_service=self.user_service,
            reminder_service=self.reminder_service,
            task_service=self.task_service,
            meeting_service=self.meeting_service,
        )

        # Initialize intelligence layer
        self.intent_resolver = IntentResolver(openai_api_key)

        # Initialize handlers
        self.command_handler = CommandHandler(
            user_service=self.user_service,
            assistant_service=self.assistant_service,
        )
        self.message_handler = MessageHandler(
            user_service=self.user_service,
            assistant_service=self.assistant_service,
            intent_resolver=self.intent_resolver,
            openai_api_key=openai_api_key,
        )
        self.callback_handler = CallbackHandler(
            user_service=self.user_service,
            assistant_service=self.assistant_service,
            intent_resolver=self.intent_resolver,
        )

        # Build application
        self.application: Optional[Application] = None

    def _build_application(self) -> Application:
        """Build the Telegram application with handlers."""
        application = Application.builder().token(self.telegram_token).build()

        # Register command handlers
        application.add_handler(TelegramCommandHandler("start", self.command_handler.start))
        application.add_handler(TelegramCommandHandler("help", self.command_handler.help))
        application.add_handler(TelegramCommandHandler("summary", self.command_handler.summary))
        application.add_handler(TelegramCommandHandler("reminders", self.command_handler.reminders))
        application.add_handler(TelegramCommandHandler("tasks", self.command_handler.tasks))
        application.add_handler(TelegramCommandHandler("meetings", self.command_handler.meetings))

        # Register message handlers
        application.add_handler(
            TelegramMessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.message_handler.handle_text,
            )
        )
        application.add_handler(
            TelegramMessageHandler(
                filters.VOICE | filters.AUDIO,
                self.message_handler.handle_audio,
            )
        )

        # Register callback handler
        application.add_handler(CallbackQueryHandler(self.callback_handler.handle_callback))

        # Error handler
        application.add_error_handler(self._error_handler)

        return application

    async def _error_handler(self, update: Update, context) -> None:
        """Handle errors."""
        logger.error(f"Update {update} caused error: {context.error}", exc_info=context.error)

        if update and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="Sorry, something went wrong. Please try again.",
                )
            except Exception:
                pass

    async def initialize(self) -> None:
        """Initialize the bot and all components."""
        logger.info("Initializing Telegram bot...")

        # Initialize intent resolver (pre-compute embeddings)
        await self.intent_resolver.initialize()

        # Build application
        self.application = self._build_application()

        logger.info("Telegram bot initialized")

    async def shutdown(self) -> None:
        """Shutdown the bot and cleanup resources."""
        logger.info("Shutting down Telegram bot...")

        if self.application:
            await self.application.shutdown()

        await self.database.disconnect()

        logger.info("Telegram bot shutdown complete")

    async def run_polling(self) -> None:
        """Run the bot using polling mode."""
        if not self.application:
            await self.initialize()

        logger.info("Starting bot in polling mode...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

        # Keep running until stopped
        import asyncio
        stop_signal = asyncio.Event()
        await stop_signal.wait()

    def run(self) -> None:
        """Run the bot (blocking call)."""
        import asyncio

        async def main():
            await self.initialize()
            await self.run_polling()

        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        finally:
            asyncio.run(self.shutdown())
