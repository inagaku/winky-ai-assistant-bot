"""Notification scheduler for sending reminders and meeting alerts."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from telegram import Bot

from app.database import Database
from app.i18n import t
from app.repositories import UserRepository, ReminderRepository, MeetingRepository
from app.services import ReminderService, MeetingService
from app.bot.keyboards import InlineKeyboards
from app.utils import utc_now

logger = logging.getLogger(__name__)


class NotificationScheduler:
    """
    Background scheduler for sending reminder and meeting notifications.

    Runs a polling loop that checks for due reminders and upcoming meetings,
    then sends notifications via Telegram.
    """

    def __init__(
        self,
        telegram_bot: Bot,
        database: Database,
        openai_api_key: str,
        check_interval_seconds: int = 60,
    ):
        self.bot = telegram_bot
        self.database = database
        self.check_interval = check_interval_seconds
        self.keyboards = InlineKeyboards()
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Initialize repositories and services
        self.user_repository = UserRepository(database)
        self.reminder_repository = ReminderRepository(database)
        self.meeting_repository = MeetingRepository(database)

        self.reminder_service = ReminderService(self.reminder_repository, openai_api_key)
        self.meeting_service = MeetingService(self.meeting_repository, openai_api_key)

    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            logger.warning("Scheduler is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Notification scheduler started")

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Notification scheduler stopped")

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                await self._check_and_send_notifications()
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}", exc_info=True)

            await asyncio.sleep(self.check_interval)

    async def _check_and_send_notifications(self) -> None:
        """Check for due reminders and meetings, send notifications."""
        now = utc_now()

        # Check reminders
        await self._process_due_reminders(now)

    async def _process_due_reminders(self, now: datetime) -> None:
        """Process and send due reminder notifications."""
        due_reminders = await self.reminder_service.get_due_reminders()

        for reminder in due_reminders:
            try:
                # Get user to find their telegram_id
                user = await self.user_repository.get_by_id(reminder.user_id)
                if not user:
                    logger.warning(f"User not found for reminder {reminder.id}")
                    continue

                # Send notification
                locale = user.preferences.language
                message = t("reminder_notification_header", locale=locale, title=reminder.title)
                if reminder.description:
                    message += f"\n\n\"{reminder.description}\""

                keyboard = self.keyboards.create_reminder_notification_keyboard(reminder_id=str(reminder.id), locale=locale)

                await self.bot.send_message(
                    chat_id=user.telegram_id,
                    text=message,
                    reply_markup=keyboard,
                    parse_mode="Markdown",
                )

                # Mark as sent
                await self.reminder_service.mark_sent(reminder.id)
                logger.info(f"Sent reminder notification: {reminder.id}")

            except Exception as e:
                logger.error(f"Failed to send reminder {reminder.id}: {e}")
